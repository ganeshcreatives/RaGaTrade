"""Offline LightGBM training with purged chronological validation.

Input must be licensed, point-in-time-adjusted 1-minute bars in CSV form with
columns symbol,timestamp,open,high,low,close,volume. Optional cross-market and
event columns are defined in features.py. The command never places orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, mean_absolute_error, precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURE_ORDER, build_features


def walk_forward_splits(frame: pd.DataFrame, horizon: int, folds: int = 4):
    """Expanding folds with an embargo of horizon bars for every instrument."""
    dates = np.array(sorted(frame.timestamp.unique()))
    if len(dates) < folds * (horizon + 40):
        raise ValueError("Not enough distinct timestamps for four purged walk-forward folds")
    blocks = np.array_split(dates, folds + 1)
    for index in range(1, len(blocks)):
        validation_dates = blocks[index]
        if not len(validation_dates):
            continue
        validation_start = validation_dates[0]
        # Time embargo based on the interval of observed bars; it scales across
        # trading calendars without converting Indian market time assumptions.
        cadence = frame.groupby("symbol").timestamp.diff().dropna().median()
        if pd.isna(cadence) or cadence <= pd.Timedelta(0):
            raise ValueError("Cannot infer bar cadence for purging overlapping labels")
        embargo_start = validation_start - cadence * horizon
        train_mask = (frame.timestamp < embargo_start) & (frame.label_end < validation_start)
        valid_mask = frame.timestamp.isin(validation_dates)
        if train_mask.sum() >= 100 and valid_mask.sum() >= 30:
            yield np.flatnonzero(train_mask.to_numpy()), np.flatnonzero(valid_mask.to_numpy())


def calibration_splits(frame: pd.DataFrame, horizon: int):
    """Keep calibration chronological, purged, and inside the outer train set."""
    splits = [(train, valid) for train, valid in walk_forward_splits(frame, horizon, folds=3)
              if frame.iloc[train].target.nunique() == 2 and frame.iloc[valid].target.nunique() == 2]
    if len(splits) < 2:
        raise ValueError("Need two chronological calibration folds with both outcome classes; import more history")
    return splits


def expected_calibration_error(labels: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (probabilities >= lower) & (probabilities < upper if upper < 1 else probabilities <= upper)
        if mask.any():
            total += mask.mean() * abs(float(labels[mask].mean()) - float(probabilities[mask].mean()))
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--horizon-bars", type=int, choices=(5, 15, 30), default=15)
    parser.add_argument("--round-trip-cost-bps", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=Path(os.getenv("MODEL_DIR", "./models")))
    args = parser.parse_args()
    if args.round_trip_cost_bps < 0 or args.round_trip_cost_bps > 500:
        parser.error("round-trip cost must be between 0 and 500 basis points")

    raw_hash = hashlib.sha256(args.csv.read_bytes()).hexdigest()
    features = build_features(pd.read_csv(args.csv))
    grouped = features.groupby(["symbol", "session_date", "segment_id"], sort=False)
    features["label_end"] = grouped["timestamp"].shift(-args.horizon_bars)
    features["future_return"] = grouped["close"].shift(-args.horizon_bars) / features["close"] - 1
    # probabilityUp is direction probability, not probability of clearing fees.
    features["target"] = (features["future_return"] > 0).astype(int)
    data = features.dropna(subset=FEATURE_ORDER + ["future_return"]).copy()
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_ORDER)
    if data["symbol"].nunique() < 2:
        raise ValueError("Provide multiple instruments to evaluate cross-sectional ranking")
    if len(data) < 600 or data["target"].nunique() < 2:
        raise ValueError("Training needs at least 600 usable rows and both outcome classes")

    x = data[FEATURE_ORDER].astype(float).to_numpy()
    y = data["target"].astype(int).to_numpy()
    returns_bps = data["future_return"].to_numpy() * 10_000
    oof_prob = np.full(len(data), np.nan)
    oof_return = np.full(len(data), np.nan)
    baseline_prob = np.full(len(data), np.nan)
    challenger_prob = np.full(len(data), np.nan)
    fold_sizes = []
    for train_ix, valid_ix in walk_forward_splits(data, args.horizon_bars):
        if np.unique(y[train_ix]).size < 2:
            continue
        base_classifier = LGBMClassifier(n_estimators=180, max_depth=4, num_leaves=15, learning_rate=0.035,
                                         reg_lambda=2.0, min_child_samples=30, verbosity=-1, n_jobs=2, random_state=17)
        champion = CalibratedClassifierCV(estimator=base_classifier, method="sigmoid", cv=calibration_splits(data.iloc[train_ix], args.horizon_bars))
        regressor = LGBMRegressor(n_estimators=180, max_depth=4, num_leaves=15, learning_rate=0.035,
                                  reg_lambda=2.0, min_child_samples=30, verbosity=-1, n_jobs=2, random_state=17)
        challenger = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=1000, class_weight="balanced"))
        champion.fit(x[train_ix], y[train_ix])
        regressor.fit(x[train_ix], returns_bps[train_ix])
        challenger.fit(x[train_ix], y[train_ix])
        oof_prob[valid_ix] = champion.predict_proba(x[valid_ix])[:, 1]
        oof_return[valid_ix] = regressor.predict(x[valid_ix])
        # A simple, transparent momentum reference; no model can beat an
        # intentionally independent no-trade baseline on economic merit alone.
        baseline_prob[valid_ix] = np.clip(0.5 + x[valid_ix, FEATURE_ORDER.index("return_5")] * 8, 0.05, 0.95)
        challenger_prob[valid_ix] = challenger.predict_proba(x[valid_ix])[:, 1]
        fold_sizes.append(int(len(valid_ix)))

    valid = np.isfinite(oof_prob)
    if valid.sum() < 100:
        raise ValueError("Purged walk-forward folds produced fewer than 100 evaluation rows")
    yy, pp, rr = y[valid], oof_prob[valid], returns_bps[valid]
    top = pp >= np.quantile(pp, 0.9)
    # Strategy-independent evaluation emphasizes classification/calibration;
    # gross returns are reported only as a descriptive research diagnostic.
    metrics = {
        "walkForwardFolds": len(fold_sizes), "validationRows": int(valid.sum()), "foldRows": fold_sizes,
        "brierScore": round(float(brier_score_loss(yy, pp)), 6),
        "calibrationError10Bins": round(expected_calibration_error(yy, pp), 6),
        "rocAuc": round(float(roc_auc_score(yy, pp)), 6) if np.unique(yy).size == 2 else None,
        "topDecilePrecision": round(float(precision_score(yy[top], np.ones(int(top.sum())), zero_division=0)), 6),
        "topDecileGrossMeanReturnBps": round(float(rr[top].mean()), 3),
        "momentumBaselineBrier": round(float(brier_score_loss(y[valid], baseline_prob[valid])), 6),
        "logisticChallengerBrier": round(float(brier_score_loss(y[valid], challenger_prob[valid])), 6),
        "challengerMeanAbsoluteErrorBps": round(float(mean_absolute_error(rr, oof_return[valid])), 3),
        "predictionIntervalBps": [round(float(v), 2) for v in np.quantile(rr - oof_return[valid], [0.05, 0.95])],
        "highVolatilityThreshold": round(float(data["volatility_20"].quantile(0.8)), 6),
        "roundTripCostBps": args.round_trip_cost_bps,
        "horizonBars": args.horizon_bars,
        "note": "Gross forward returns are not a strategy backtest. No promotion or trading approval is implied.",
    }

    base_classifier = LGBMClassifier(n_estimators=180, max_depth=4, num_leaves=15, learning_rate=0.035,
                                     reg_lambda=2.0, min_child_samples=30, verbosity=-1, n_jobs=2, random_state=17)
    champion = CalibratedClassifierCV(estimator=base_classifier, method="sigmoid", cv=calibration_splits(data, args.horizon_bars))
    regressor = LGBMRegressor(n_estimators=180, max_depth=4, num_leaves=15, learning_rate=0.035,
                              reg_lambda=2.0, min_child_samples=30, verbosity=-1, n_jobs=2, random_state=17)
    champion.fit(x, y)
    regressor.fit(x, returns_bps)
    artifact = {"classifier": champion, "regressor": regressor, "featureOrder": FEATURE_ORDER}
    args.output.mkdir(parents=True, exist_ok=True)
    temporary = args.output / "candidate.joblib.tmp"
    joblib.dump(artifact, temporary, compress=3)
    artifact_hash = hashlib.sha256(temporary.read_bytes()).hexdigest()
    candidate = args.output / f"candidate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.joblib"
    temporary.replace(candidate)
    manifest = {"modelVersion": f"lgbm-{artifact_hash[:12]}", "modelFamily": "LightGBM",
                "trainedAt": datetime.now(timezone.utc).isoformat(), "trainingRows": int(len(data)),
                "symbols": sorted(data.symbol.unique().tolist()), "horizonMinutes": args.horizon_bars,
                "featureOrder": FEATURE_ORDER, "metrics": metrics, "artifactSha256": artifact_hash,
                "datasetSha256": raw_hash, "approval": "CANDIDATE_NOT_PROMOTED", "source": "OFFLINE_TRAINING"}
    manifest_path = args.output / f"{candidate.stem}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"candidateArtifact": str(candidate), "candidateManifest": str(manifest_path),
                      "modelVersion": manifest["modelVersion"], "metrics": metrics,
                      "promotion": "Not promoted. Review source rights, data quality, metrics and stability before approval."}, indent=2))


if __name__ == "__main__":
    main()
