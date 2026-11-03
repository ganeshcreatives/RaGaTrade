"""Inference API for versioned, offline-trained research models.

This process only returns research estimates. It has no broker credentials and
cannot submit an order. The service fails closed to NO_TRADE when no validated
artifact is installed or the input market data is stale.
"""
from __future__ import annotations

import json
import hashlib
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import AnyHttpUrl, AwareDatetime, BaseModel, Field, field_validator

from features import FEATURE_ORDER, build_features

MODEL_DIR = Path(os.getenv("MODEL_DIR", "/models"))
ARTIFACT = MODEL_DIR / "active.joblib"
MANIFEST = MODEL_DIR / "active.json"
MAX_DATA_AGE_MS = int(os.getenv("MAX_DATA_AGE_MS", "30000"))
app = FastAPI(title="MarketPilot Research ML", version="1.0.0", description="Offline-trained market research inference; no trading permissions.")


class PredictRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    horizon_minutes: int = Field(default=15, ge=5, le=30)
    data_freshness_ms: int = Field(ge=0)
    data_as_of: AwareDatetime
    features: dict[str, float] = Field(default_factory=dict)
    source: str = Field(default="UNKNOWN", max_length=40)


class BarInput(BaseModel):
    timestamp: AwareDatetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)


class FeatureRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    bars: list[BarInput] = Field(min_length=21, max_length=500)


class EventRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=100)
    source_url: AnyHttpUrl
    published_at: datetime | None = None
    first_seen_at: datetime
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(default="", max_length=10000)

    @field_validator("source_url")
    @classmethod
    def require_https_source(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("Event source URL must use HTTPS")
        return value


def status() -> dict[str, Any]:
    if not (ARTIFACT.is_file() and MANIFEST.is_file()):
        return {"status": "untrained", "modelVersion": None, "modelFamily": "LightGBM", "trainedAt": None,
                "trainingRows": 0, "metrics": None, "source": "NO_MODEL", "action": "NO_TRADE"}
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unavailable", "modelVersion": None, "source": "INVALID_MANIFEST", "action": "NO_TRADE"}
    if not isinstance(manifest, dict):
        return {"status": "unavailable", "source": "INVALID_MANIFEST", "action": "NO_TRADE"}
    if manifest.get("approval") != "HUMAN_APPROVED" or not manifest.get("reviewer") or not manifest.get("approvalNote"):
        return {"status": "unavailable", "source": "UNAPPROVED_MODEL", "action": "NO_TRADE"}
    try:
        valid_hash = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == manifest.get("artifactSha256")
    except OSError:
        valid_hash = False
    if not valid_hash or manifest.get("featureOrder") != FEATURE_ORDER:
        return {"status": "unavailable", "source": "INVALID_ARTIFACT", "action": "NO_TRADE"}
    return {**manifest, "status": "ready"}


@app.get("/health")
def health() -> dict[str, Any]:
    current = status()
    return {"status": "ok", "service": "ml-service", "model": current.get("modelVersion"),
            "modelStatus": current["status"], "liveExecution": False}


@app.get("/internal/ml/model/status")
def model_status() -> dict[str, Any]:
    return status()


@app.post("/internal/ml/features")
def calculate_features(body: FeatureRequest) -> dict[str, Any]:
    rows = [{**bar.model_dump(), "symbol": body.symbol} for bar in body.bars]
    frame = build_features(pd.DataFrame(rows))
    if frame.empty or frame.iloc[-1][FEATURE_ORDER].isna().any():
        raise HTTPException(status_code=422, detail="Not enough valid bars to calculate the feature window")
    last = frame.iloc[-1]
    return {"symbol": body.symbol.upper(), "dataAsOf": last["timestamp"].isoformat(),
            "features": {name: float(last[name]) for name in FEATURE_ORDER}, "source": "POINT_IN_TIME_FEATURES"}


@app.post("/internal/ml/events/classify")
def classify_event(body: EventRequest) -> dict[str, Any]:
    """Optional local FinBERT classification; never fetches URLs or creates advice."""
    model_path = os.getenv("FINBERT_MODEL_PATH", "")
    if not model_path or not Path(model_path).is_dir():
        raise HTTPException(status_code=503, detail="A reviewed local FinBERT model is not configured")
    try:
        from event_nlp import classify
        result = classify(model_path, f"{body.title}\n{body.text}")
    except (ImportError, OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"Event classifier unavailable: {type(exc).__name__}") from exc
    return {"sourceId": body.source_id, "sourceUrl": str(body.source_url),
            "publishedAt": body.published_at.isoformat() if body.published_at else None,
            "firstSeenAt": body.first_seen_at.isoformat(), "classification": result,
            "impact": "UNASSESSED", "tradingAction": "NONE",
            "disclaimer": "Text classification is unverified context, not an impact forecast or order instruction."}


@app.post("/internal/ml/predict")
def predict(body: PredictRequest) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    if body.data_as_of > now:
        raise HTTPException(status_code=422, detail="Market timestamp must not be in the future")
    computed_freshness_ms = max(0, int((now - body.data_as_of.astimezone(timezone.utc)).total_seconds() * 1000))
    data_freshness_ms = max(body.data_freshness_ms, computed_freshness_ms)
    as_of = body.data_as_of.astimezone(timezone.utc).isoformat()
    current = status()
    if data_freshness_ms > MAX_DATA_AGE_MS:
        return {"symbol": body.symbol.upper(), "asOf": as_of, "horizonMinutes": body.horizon_minutes,
                "probabilityUp": None, "expectedReturnBps": None, "predictionIntervalBps": None,
                "marketRegime": "unknown", "dataFreshnessMs": data_freshness_ms,
                "modelVersion": current.get("modelVersion"), "modelStatus": current["status"],
                "action": "NO_TRADE", "reason": "Market input is stale; inference was suppressed.", "source": body.source}
    if body.source != "POINT_IN_TIME_FEATURES":
        return {"symbol": body.symbol.upper(), "asOf": as_of, "horizonMinutes": body.horizon_minutes,
                "probabilityUp": None, "expectedReturnBps": None, "predictionIntervalBps": None,
                "marketRegime": "unknown", "dataFreshnessMs": data_freshness_ms,
                "modelVersion": current.get("modelVersion"), "modelStatus": current["status"],
                "action": "NO_TRADE", "reason": "A timestamped, point-in-time feature snapshot is required; synthetic or quote-only inputs are not scored.",
                "source": body.source}
    if current["status"] != "ready":
        return {"symbol": body.symbol.upper(), "asOf": as_of, "horizonMinutes": body.horizon_minutes,
                "probabilityUp": None, "expectedReturnBps": None, "predictionIntervalBps": None,
                "marketRegime": "unknown", "dataFreshnessMs": data_freshness_ms,
                "modelVersion": None, "modelStatus": current["status"], "action": "NO_TRADE",
                "reason": "No approved model artifact is installed. Load point-in-time licensed data, train and review a model first.",
                "source": "NO_MODEL"}
    if body.horizon_minutes != current.get("horizonMinutes"):
        return {"symbol": body.symbol.upper(), "asOf": as_of, "horizonMinutes": body.horizon_minutes,
                "probabilityUp": None, "expectedReturnBps": None, "predictionIntervalBps": None,
                "marketRegime": "unknown", "dataFreshnessMs": body.data_freshness_ms,
                "modelVersion": current.get("modelVersion"), "modelStatus": "ready", "action": "NO_TRADE",
                "reason": "The active artifact was trained for a different forecast horizon.", "source": body.source}
    try:
        artifact_bytes = ARTIFACT.read_bytes()
        if hashlib.sha256(artifact_bytes).hexdigest() != current.get("artifactSha256"):
            raise ValueError("Model changed during inference; retry after promotion completes")
        artifact = joblib.load(io.BytesIO(artifact_bytes))
        feature_order = current["featureOrder"]
        row = np.asarray([[float(body.features[name]) for name in feature_order]], dtype=np.float64)
        if not np.isfinite(row).all():
            raise ValueError("Non-finite feature")
        probability = float(artifact["classifier"].predict_proba(row)[0, 1])
        expected_bps = float(artifact["regressor"].predict(row)[0])
        low, high = current["metrics"]["predictionIntervalBps"]
        if not np.isfinite([probability, expected_bps, low, high]).all() or not 0 <= probability <= 1 or low > high:
            raise ValueError("Invalid model output")
        volatility = float(body.features.get("volatility_20", 0.0))
        regime = "high_volatility" if volatility >= current["metrics"].get("highVolatilityThreshold", 0.025) else "normal"
        return {"symbol": body.symbol.upper(), "asOf": as_of, "horizonMinutes": body.horizon_minutes,
                "probabilityUp": round(probability, 4), "expectedReturnBps": round(expected_bps, 2),
                "predictionIntervalBps": [round(expected_bps + low, 2), round(expected_bps + high, 2)], "marketRegime": regime,
                "dataFreshnessMs": data_freshness_ms, "modelVersion": current["modelVersion"],
                "modelStatus": "ready", "action": "NO_TRADE",
                "reason": "Research estimate only. Automated trade decisions are disabled; validate uncertainty and costs independently.",
                "source": body.source}
    except (KeyError, ValueError, OSError, IndexError) as exc:
        raise HTTPException(status_code=422, detail=f"Model input/artifact is invalid: {type(exc).__name__}") from exc
