# MarketPilot quantitative research engine

The service is isolated from broker credentials and has no order-submission
route. Inference is a research aid; its response always sets `action` to
`NO_TRADE`. A missing model, stale quote, synthetic input, or incomplete
feature snapshot produces a missing estimate and a reason instead of a guessed
probability.

## Model workflow

1. Sign in to the app, connect Dhan, and use **AI research → Import licensed
   Dhan history** for at least two supported instruments. Each import is
   restricted to 90 days and stored in `market_bars_1m`; Dhan entitlement and
   exchange terms control retention and analysis rights. Export the selected
   window with **Download stored bars**. Never train on today's reconstructed
   history as if it had been available at the time.
2. Include at least two symbols and 600 usable rows after the rolling warmup.
   Optional point-in-time columns are `market_return_5`, `sector_return_5`,
   `usd_inr_change`, `brent_change`, `sentiment_score`, and `event_confidence`.
   Omitted optional columns are set to zero and therefore must also be zeroed
   at inference. Do not mix source definitions across training and inference.
3. Train a LightGBM direction classifier and return regressor. The CLI reports
   expanding chronological folds with a horizon-sized embargo, calibration,
   top-decile precision, gross forward return, and logistic/momentum
   comparators. Gross return is not strategy P&L and fees/market impact remain
   an explicit assumption.
4. Review the dataset hash, rights, corporate actions, symbol coverage,
   fold stability, cost sensitivity, calibration, drawdown/turnover in a
   separate strategy backtest, and a shadow period. The promotion CLI checks
   minimum validation rows/folds, Brier score versus both comparators, and
   calibration error; a named human reviewer and note are also mandatory.
5. Promotion copies the approved candidate to `models/active.joblib` and
   writes `models/active.json`. The mounted model directory is local-only in
   Compose. Cloud artifacts need an approved durable store before deployment.

Example (run from repository root):

```powershell
python -m pip install -r services/ml-service/requirements.txt
python services/ml-service/train.py C:\data\licensed-bars.csv --horizon-bars 15 --round-trip-cost-bps 20
python services/ml-service/promote.py .\models\candidate-<timestamp>.joblib --reviewer "operator-id" --approval-note "Reviewed point-in-time rights, validation, stability and cost sensitivity"
```

The model must not be considered production-ready just because it passes these
mechanical gates. The chosen architecture still needs exchange calendar and
corporate-action sources, licensed historical data, event/news rights, robust
net-of-cost strategy backtests, drift monitoring, and independent approval.
Optional local FinBERT event sentiment is wired at
`POST /internal/ml/events/classify`. Install `requirements-nlp.txt` and set
`FINBERT_MODEL_PATH` to an already reviewed, local model directory to enable
it. The service does not download model weights or fetch article URLs. The
response keeps source URL and both timestamps, reports classification
confidence, leaves impact `UNASSESSED`, and has no trading action. No paid
LLM/event extraction is connected: a licensed content source, model/provider,
data-handling policy, and cloud budget must be selected first. LLM output must
never authorize or route orders.

## Feature contract

`return_1`, `return_3`, `return_5`, and `return_10` are close-to-close returns;
`volatility_20` is the rolling standard deviation of one-bar returns;
`relative_volume_20` compares volume to the prior 20-bar mean;
`vwap_distance` uses a rolling 20-bar typical-price VWAP;
`range_pct` is high-low divided by close; `momentum_5_20` is the five-bar
return less the twenty-bar return. Market, sector, FX, commodity, and event
features are optional and must be timestamped no later than the feature row.

The inference API accepts `POST /internal/ml/predict` with a complete feature
map and `source: "POINT_IN_TIME_FEATURES"`. It is internal to the application
network. `/internal/ml/model/status` reports whether an approved model is
mounted. `/health` includes the model state. Do not expose these routes publicly.

## Verification and model semantics

Run `python -m unittest discover -s services/ml-service/tests -v` after installing
`requirements.txt` and `httpx`. CI now requires these tests, TypeScript checks,
and the frontend/API build before publishing images. Synthetic test fixtures
are isolated from application data and never promoted or deployed as models.

Feature windows and labels stop at missing minutes and session boundaries.
Both outer validation and inner probability calibration are chronological;
training labels must end before the next validation window. `probabilityUp`
means a positive forward return. Costs are separately reported assumptions.
The prediction interval adds validation residual quantiles to the predicted
return. This is an empirical interval, not a guaranteed confidence bound.
Inference verifies approval and artifact SHA-256 before loading the model,
rejects future or timezone-free input timestamps, and retains the data's
as-of timestamp. Artifact and manifest storage must remain operator-controlled.
