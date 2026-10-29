# MarketPilot — full local research and paper-trading application

This repository contains an end-to-end local application based on `ai_trading_architecture.html`: responsive React research workspace, Node/Express API, PostgreSQL persistence, cookie-based email/password identity, watchlists, forecasts, global-event records, paper OMS with transactional order/position/cash-ledger updates, account risk defaults, an isolated FastAPI inference service, Redis-backed sample quotes, a Dhan OAuth/read-only quote adapter, operations view and Docker Compose stack.

## Start the complete stack

Install Docker Desktop and Node.js 20+.

1. Copy `.env.example` to `.env`.
2. Set `JWT_SECRET` in `.env` to a random secret at least 32 characters long.
3. Set `DHAN_TOKEN_ENCRYPTION_KEY` to a random 32-byte hex string. Keep `.env` private; it is ignored by Git.
4. From the repository root run `docker compose -f infra/docker-compose.yml up --build`.
5. Open `http://localhost:5173`, register/sign in, open **Broker setup**, and choose **Connect Dhan**.

Services are exposed at web `5173`, API `4000`, PostgreSQL `5432`, Redis `6379`, and FastAPI `8000`. The API waits for PostgreSQL, initializes the relational schema, and seeds the sample instrument and event records. Local dev mode can run Postgres and Redis with Compose, then `npm install` and `npm run dev` for hot reload. The API runs at `http://localhost:4000`; Vite runs at `http://localhost:5173`.

## Implemented user journeys

- Public visitor: browse a sample market overview, screen instruments by name/sector, inspect an instrument chart and its baseline estimate, and read sample global-event records.
- Registered user: create a local account, sign in and sign out. Passwords are bcrypt-hashed; session tokens are signed and stored in HttpOnly SameSite cookies; sign-in/registration requests are rate limited.
- Personal research: add/remove instruments in a persistent user-owned watchlist.
- Paper trading: each account starts with configurable virtual cash; user can submit market orders; a transaction locks the account, checks cash/position/deployment/loss limits, records a fill and fee, updates positions/cash, appends ledger rows and records an audit event atomically.
- Portfolio: review marked equity, cash, positions, orders, fees, ledger, and configured paper-risk defaults.
- Research: inspect model version, estimate horizon, illustrative uncertainty and the documented evaluation criteria. Forecast requests are stored in PostgreSQL.
- Operations: administrator-only service status and counts. Promote a local account manually after sign-up with SQL: `UPDATE users SET role='admin' WHERE email='you@example.com';`.

## Dhan setup and market-data boundary

The app reads `DHAN_API_KEY`, `DHAN_API_SECRET`, `DHAN_CLIENT_ID`, `DHAN_REDIRECT_URI`, `DHAN_LOGIN_EMAIL`, and `DHAN_TOKEN_ENCRYPTION_KEY` from the local `.env`. Configure the exact redirect URL `http://localhost:4000/api/v1/dhan/callback` in the Dhan API key settings before using Connect Dhan. Complete login and any verification on Dhan's official page. The API stores the resulting token encrypted in PostgreSQL; it is never sent to the browser. Tokens expire and must be reauthorized through Broker setup. Dhan's Data APIs may require a separate subscription. The Dhan flow follows [Dhan's API key authentication documentation](https://dhanhq.co/docs/v2/authentication/).

Mapped NSE equity quotes are polled from Dhan when connected. Redis sample quotes remain a fallback. Index levels, chart candles, backtest inputs, global event cards and forecasts are synthetic and must not be interpreted as verified market or investment research. Historical Dhan candles are not yet wired into chart/backtest results.

## Explicit execution boundary

When Dhan is disconnected, equity quotes are fabricated sample data; with a valid Dhan connection, mapped equity quotes may come from Dhan. Synthetic fallback values are labeled. Index values, candles, events and forecasts remain sample data. The ML service is a baseline proxy and is not trained, calibrated, or backtested. These values are for UI and engineering demonstration only and must not guide financial decisions.

The paper OMS is implemented and persistent, but its fill assumptions are deliberately simple: immediate marketable fills with fixed illustrative slippage and fees. It is not a realistic exchange queue or a substitute for official market-session calendars, circuit/auction rules, current statutory charges, or broker reconciliation. Risk limits are starting defaults, not validated policy recommendations.

Live order routes are hard-disabled in the API. Dhan connection only supports OAuth and market data; no setting can activate broker orders. Public redistribution, news subscriptions, Google OAuth, verified email/password reset, MFA, compliance approvals, and Azure deployment credentials need provider contracts/secrets and separate implementation/approval. Azure login/configuration will be added after the user provides those details.

## API routes

Public: `GET /health`, `GET /api/v1/overview`, `GET /api/v1/instruments?q=&sector=`, `GET /api/v1/market/:id/candles`, `GET /api/v1/insights/:id`, `GET /api/v1/global/events`.

Identity: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`.

Authenticated: `GET/POST/DELETE /api/v1/watchlist[/:instrumentId]`, `GET /api/v1/paper/account`, `POST /api/v1/paper/orders`, `GET /api/v1/paper/ledger`, `GET /api/v1/risk/policy`, `POST /api/v1/dhan/connect`, `GET /api/v1/dhan/callback`, `GET /api/v1/dhan/status`, `GET /api/v1/dhan/profile`, and `POST /api/v1/dhan/disconnect`.

Admin only: `GET /api/v1/admin/health`. Live gate: `GET /api/v1/live/status`, `POST /api/v1/live/order-intents` (always blocked).

## Structure

- `apps/web`: React 18, TypeScript, Vite, Recharts, Lucide
- `apps/api`: Express, PostgreSQL (`pg`), Zod, bcrypt, JWT cookie sessions and rate limits
- `services/ml-service`: FastAPI/Pydantic inference interface
- `services/market-worker`: synthetic fallback quote publisher to Redis
- `services/trading-worker`: isolated paper-mode worker process; no broker connector
- `database/schema.sql`: identity, instrument, watchlist, forecast, paper OMS/ledger, audit, risk and event tables
- `infra/docker-compose.yml`: web, API, PostgreSQL, Redis, ML and worker services

## Database notes

The API creates tables and seeds supported demo instruments on start. The Compose Postgres volume persists between restarts. To reset a disposable local environment, stop Compose and remove its `pgdata` volume, then restart. Existing environments created by earlier schema versions may require a database reset or a migration; do not reset a database containing user data.
