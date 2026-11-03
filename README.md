# MarketPilot — AI market research and paper-trading platform

Full-stack local project based on `ai_trading_architecture.html`. The isolated ML service includes an offline LightGBM candidate trainer, purged walk-forward evaluation, challenger metrics, artifact hashes, and a human-reviewed promotion command. It deliberately does not score demo quotes and returns `NO_TRADE` unless a complete point-in-time feature snapshot and approved model are available.

## Run

1. Copy `.env.example` to `.env` and replace `JWT_SECRET` with a random secret of 32+ characters.
2. Run `docker compose -f infra/docker-compose.yml up --build`.
3. Open `http://localhost:5173` and register an account.

For hot reload, start the Postgres/Redis/ML containers and run `npm install` then `npm run dev` from the project root.

Implemented: responsive React dashboard, searchable sector screener, instrument detail/chart, research interface, global event feed, local account registration/sign-in, persistent watchlists, paper accounts, transactional order/position/cash ledger, risk checks, audit events, admin status panel, Python inference/training service, Redis sample quote worker, Dhan OAuth connection with encrypted token storage and read-only quote polling, and a local Compose stack.

## Quantitative AI engine

See [services/ml-service/README.md](services/ml-service/README.md) for CSV requirements, engineered feature contract, offline LightGBM training, purged walk-forward validation, benchmark comparisons, artifact hashes and human promotion. Models require licensed, timestamped, point-in-time adjusted bars. No dataset or model is bundled. Synthetic/demo data is rejected by inference. Model output is research-only and `NO_TRADE`; it cannot call a broker.

Demo chart candles, index values, and sample events are marked synthetic. Backtests require imported Dhan history and return a clear error if the requested bars are unavailable. Authenticated users can import up to 90 days of Dhan historical candles at a time and export stored bars; API entitlement and data-use terms apply. Live Dhan order execution is not implemented and is hard-disabled. Azure PostgreSQL and Key Vault exist, but the database is network-isolated and the app is not deployed. See the local `AZURE_ACCOUNT_REFERENCE.md` for Azure status and [docs/README.md](docs/README.md) for application setup and API routes.
