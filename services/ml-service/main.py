from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Trading ML Service", version="0.1.0", description="Baseline research estimates; never routes orders.")

class PredictRequest(BaseModel):
    symbol: str
    last_price: float = Field(gt=0)
    change_pct: float = 0.0
    horizon_minutes: int = Field(default=15, ge=1, le=240)
    data_freshness_ms: int = Field(default=0, ge=0)

@app.get("/health")
def health():
    return {"status": "ok", "service": "ml-service", "model": "baseline-demo-v0.1"}

@app.post("/internal/ml/predict")
def predict(body: PredictRequest):
    probability = max(0.35, min(0.65, 0.5 + body.change_pct / 20))
    return {"symbol": body.symbol.upper(), "asOf": datetime.now(timezone.utc).isoformat(), "horizonMinutes": body.horizon_minutes, "probabilityUp": round(probability, 2), "expectedReturnBps": round(body.change_pct * 5), "predictionIntervalBps": [-38, 54], "marketRegime": "unknown", "dataFreshnessMs": body.data_freshness_ms, "modelVersion": "baseline-demo-v0.1", "action": "NO_TRADE", "reason": "Unvalidated illustrative estimate; no edge established after costs.", "source": "DEMO_MODEL"}
