"""Point-in-time technical and cross-market features for minute-bar research."""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_ORDER = [
    "return_1", "return_3", "return_5", "return_10", "volatility_20",
    "relative_volume_20", "vwap_distance", "range_pct", "momentum_5_20",
    "market_return_5", "sector_return_5", "usd_inr_change", "brent_change",
    "sentiment_score", "event_confidence",
]
OPTIONAL_FEATURES = FEATURE_ORDER[9:]


def build_features(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"Missing required CSV columns: {', '.join(sorted(missing))}")
    frame = bars.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["symbol", "timestamp", "open", "high", "low", "close", "volume"])
    numeric = frame[["open", "high", "low", "close", "volume"]]
    frame = frame[np.isfinite(numeric).all(axis=1) & (numeric[["open", "high", "low", "close"]] > 0).all(axis=1)
                  & (frame["volume"] >= 0) & (frame["low"] <= frame[["open", "close"]].min(axis=1))
                  & (frame["high"] >= frame[["open", "close"]].max(axis=1))]
    frame = frame.sort_values(["symbol", "timestamp"], kind="stable").drop_duplicates(["symbol", "timestamp"], keep="last")
    # Never treat an overnight/session boundary as a one-minute return. The
    # exchange session date is derived from India local time even though stored
    # timestamps are UTC.
    frame["session_date"] = frame["timestamp"].dt.tz_convert("Asia/Kolkata").dt.date
    # A missing minute invalidates rolling context and forward labels across
    # the gap. Rebuild a complete window before emitting another feature row.
    gaps = frame.groupby("symbol", sort=False)["timestamp"].diff().ne(pd.Timedelta(minutes=1))
    frame["segment_id"] = gaps.groupby(frame["symbol"], sort=False).cumsum()
    groups = frame.groupby(["symbol", "session_date", "segment_id"], sort=False)
    close = groups["close"]
    features = pd.DataFrame(index=frame.index)
    for period in (1, 3, 5, 10):
        features[f"return_{period}"] = close.pct_change(period)
    features["volatility_20"] = groups["close"].transform(lambda s: s.pct_change().rolling(20, min_periods=20).std(ddof=0))
    features["relative_volume_20"] = frame["volume"] / groups["volume"].transform(lambda s: s.shift(1).rolling(20, min_periods=20).mean()).replace(0, np.nan)
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    vwap_num = (typical * frame["volume"]).groupby([frame["symbol"], frame["session_date"], frame["segment_id"]], sort=False).transform(lambda s: s.rolling(20, min_periods=20).sum())
    vwap_den = groups["volume"].transform(lambda s: s.rolling(20, min_periods=20).sum()).replace(0, np.nan)
    features["vwap_distance"] = (frame["close"] / (vwap_num / vwap_den)) - 1
    features["range_pct"] = (frame["high"] - frame["low"]) / frame["close"]
    features["momentum_5_20"] = groups["close"].transform(lambda s: s.pct_change(5) - s.pct_change(20))
    for name in OPTIONAL_FEATURES:
        features[name] = pd.to_numeric(frame[name], errors="coerce") if name in frame else 0.0
    result = frame[["symbol", "session_date", "segment_id", "timestamp", "open", "high", "low", "close", "volume"]].join(features)
    return result.replace([np.inf, -np.inf], np.nan)
