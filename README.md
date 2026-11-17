# RaGaTrade

RaGaTrade is a research and paper-trading application built from `ai_trading_architecture.html`. The live Azure app uses PostgreSQL, a React web client, a Node API, an isolated FastAPI research service, and DhanHQ for read-only NSE market data.

## Run locally

1. Copy `.env.example` to `.env` and set a random `JWT_SECRET` (at least 32 characters) and a 32-byte hex `DHAN_TOKEN_ENCRYPTION_KEY`.
2. Run `docker compose -f infra/docker-compose.yml up --build`.
3. Open `http://localhost:5173`, register/sign in, then connect Dhan in **Broker setup**.

The Compose stack provides the web app, API, PostgreSQL, Redis cache, and ML service. At startup the API syncs the public Dhan NSE equity instrument master before listening. If the instrument source is unavailable, it does not seed substitute prices or a fabricated stock list. Redis is only a cache for verified Dhan API quotes.

For hot reload, start the infrastructure services with Compose, then run `npm install` and `npm run dev` from the root. Never commit `.env`, Dhan credentials, access tokens, or model datasets.

## Real data boundary

- The API catalog is synced from Dhan's official instrument master. Dhan market quotes are polled for NSE equities in batches; no fixture or sample quote is used as a fallback.
- A Dhan access token is user supplied through the secure broker setup form, verified against Dhan profile, encrypted in PostgreSQL, and renewed by the Azure hourly job while it is active. Dhan Web tokens last 24 hours; renewal can still fail if Dhan revokes a token or the job is unavailable.
- Historical candles are shown only after Dhan history is imported. Automatic incremental sync runs when a signed-in user opens AI Research for an equity with missing or stale history.
- No index feed, licensed news/event source, approved forecasting model, or public market-data redistribution entitlement is configured. Those areas display unavailable states; the app does not invent content or forecasts.
- Live broker order routes remain hard-disabled. Paper fills use simplified assumptions and are not exchange-realistic.

Dhan data is subject to the account's active API subscription and Dhan/exchange data-use terms. Do not redistribute it publicly without the required rights. See [Dhan authentication](https://dhanhq.co/docs/v2/authentication/), [market quotes](https://dhanhq.co/docs/v2/market-quote/), and [historical data](https://dhanhq.co/docs/v2/historical-data/).

## AI research

The CPU LightGBM workflow supports point-in-time OHLCV feature generation, purged chronological evaluation, benchmark comparisons, calibration checks, artifact hashes, and human approval gates. No training dataset or approved model is included. The current historical-data candidate failed its evaluation gate, so forecast output remains `NO_TRADE`/unavailable. See [services/ml-service/README.md](services/ml-service/README.md).

## Architecture and status

See [docs/architecture.md](docs/architecture.md) for current service boundaries and [docs/completion-report.md](docs/completion-report.md) for verified work and remaining blockers. `AZURE_ACCOUNT_REFERENCE.md` is local and Git-ignored; it contains private Azure account/resource navigation details.
