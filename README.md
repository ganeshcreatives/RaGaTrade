# MarketPilot — AI market research and paper-trading platform

Full-stack local project based on `ai_trading_architecture.html`.

## Run

1. Copy `.env.example` to `.env` and replace `JWT_SECRET` with a random secret of 32+ characters.
2. Run `docker compose -f infra/docker-compose.yml up --build`.
3. Open `http://localhost:5173` and register an account.

For hot reload, start the Postgres/Redis/ML containers and run `npm install` then `npm run dev` from the project root.

Implemented: responsive React dashboard, searchable sector screener, instrument detail/chart, AI baseline explanation, global event feed, local account registration/sign-in, persistent watchlists, persistent paper accounts, transactional order/position/cash ledger, risk checks, audit events, admin status panel, Python inference service, Redis sample quote worker, Dhan OAuth connection with encrypted local token storage and read-only quote polling, and a full local Compose stack.

Sample chart candles, backtest history, index values, events and forecasts remain marked synthetic. Dhan can provide quotes for mapped NSE equities after you finish OAuth in the app; data API entitlement may apply. Live Dhan order execution is not implemented and is hard-disabled. Azure configuration is deferred until you provide the login and subscription details. Read [docs/README.md](docs/README.md) for complete routes, setup and scope details.
