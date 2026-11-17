# RaGaTrade application guide

RaGaTrade consists of a React/Vite web client, Express API, PostgreSQL database, Redis quote cache, and isolated FastAPI research service. It uses DhanHQ for read-only NSE market data and keeps all orders in the local paper account.

## Local setup

Install Docker Desktop and Node.js 20+. Copy `.env.example` to `.env`, set a random `JWT_SECRET` with at least 32 characters and a 32-byte hex `DHAN_TOKEN_ENCRYPTION_KEY`, then run from the repository root:

```powershell
docker compose -f infra/docker-compose.yml up --build
```

Open `http://localhost:5173`, register/sign in, and use **Broker setup → Connect Dhan**. Complete Dhan consent in the Dhan page. The OAuth callback for local development is `http://localhost:4000/api/v1/dhan/callback`; the Azure callback is recorded in the private `AZURE_ACCOUNT_REFERENCE.md`. Do not paste credentials or access tokens into chat, source files, or issue trackers.

The API syncs the Dhan instrument master before it starts listening and refreshes it daily. If sync fails on an empty database, the instrument list is empty rather than filled with sample symbols/prices. The only quote cache source is a successful Dhan API response. No index or event/news provider is connected.

## Data and model behavior

- Market quotes are read-only Dhan snapshots. Missing, expired, or rejected data stays unavailable; no sample quote is substituted.
- Historical chart bars come from imported Dhan candles. AI Research syncs when the selected equity has no saved history or its newest bar is older than 36 hours. Entitlement, rate limits, and data-use terms apply.
- Training accepts licensed point-in-time data only. The included model pipeline is not an approved model; the current trained candidate failed validation. The engine returns no estimate until a new candidate passes review and is approved.
- Global event/news panels remain empty because no verified provider is connected.
- The paper OMS uses simplified assumed fills, fixed illustrative costs and deterministic risk checks. It is not a realistic exchange simulator. Live broker order APIs are hard-disabled.

## Useful routes

Public service health and catalog routes: `GET /health`, `GET /api/v1/overview`, `GET /api/v1/instruments?q=&sector=`, `GET /api/v1/market/:id/candles`, `GET /api/v1/insights/:id`, `GET /api/v1/global/events`.

Identity routes: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`.

Authenticated routes include watchlists, paper account/orders/ledger, risk policy, Dhan connect/status/profile, history import/export, and backtests. Live order status is permanently disabled in this release.

## Project map

- `apps/web`: React interface and charts
- `apps/api`: identity, catalog sync, Dhan integration, paper OMS and REST routes
- `services/ml-service`: isolated LightGBM training/inference and artifact approval tooling
- `database/schema.sql`: PostgreSQL schema
- `infra/docker-compose.yml`: local web, API, PostgreSQL, Redis and ML services
- `ai_trading_architecture.html`: target product architecture

For current deployment IDs, Azure navigation, budget and operational records, see the local Git-ignored `AZURE_ACCOUNT_REFERENCE.md`. For verified implementation status and remaining production gates, see [completion-report.md](completion-report.md).
