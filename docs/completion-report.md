# RaGaTrade implementation and verification report

Date: 3 November 2026 (India time)
Reference: `ai_trading_architecture.html`. This is an implementation inventory, not a production readiness certificate.

## Overall result

The development application is deployed, but the full architecture is **not complete**.
The live Dhan connection requires the user's consent session to finish. A paid Data API
plan and app key/secret do not replace that step. No real training dataset or reviewed
model artifact has been installed. Missing data remains unavailable; models return NO_TRADE.

## Architecture coverage

| Area | Implemented | Remaining and reason |
|---|---|---|
| Frontend | React dashboard, instruments, watchlist, paper portfolio, alerts, research, broker setup | Comprehensive browser/mobile/accessibility acceptance testing remains |
| Identity | Email/password login, hashed passwords, server sessions, user-scoped routes; Google adapter | Email verification, password recovery, MFA and Google provider configuration are not complete |
| Backend/data | Express, PostgreSQL schema, persisted accounts/orders/ledger/audit; request validation | Migration tooling, broad contract coverage and stronger operational controls remain |
| Dhan connection | Server consent generation/exchange, encrypted token storage, disconnect/profile routes; server callback configuration | User must finish consent; root redirect compatibility added after observing Dhan return to the homepage |
| Market quotes | Read-only polling for nine mapped NSE equities, unavailable-state handling | Full instrument master, Dhan WebSocket worker, order-book depth, exchange timestamps and licensed index data are not implemented |
| History | Dhan one-minute import with OHLCV validation, database persistence, CSV export | Real imports still depend on Dhan connection; corporate actions, exchange calendar, historical gap reconciliation and archive pipeline remain |
| Feature engine | Returns, volatility, relative volume, rolling VWAP, range and momentum | Optional cross-market/event fields have no providers; missing fields are neutral placeholders, not observations |
| Model training | LightGBM direction classifier/return regressor, chronological purged evaluation and calibration, logistic/momentum comparisons | No real candidate trained; XGBoost challenger, multi-horizon registry, shadow comparison and drift monitoring remain |
| Model inference | Approval/hash checks, data-age and timestamp guards, empirical return intervals, NO_TRADE without model | No approved active artifact; inference has not been validated with a real trained model |
| News/global intelligence | Event schema and optional local FinBERT adapter | No source ingestion, installed FinBERT weights, LLM provider, macro/FX/commodity feeds or evidence-verification workflow |
| Paper execution | API-driven market-order simulation, balance/position/risk checks and persisted ledger | Trading worker is a placeholder; limit/stop/partial-fill state machine, realistic liquidity/slippage, versioned statutory fees, session automation and replay tests remain |
| Live execution | Server-side disabled routes | Broker order adapter/reconciliation and full live execution are absent; separate broker, risk and operational approval remains required |
| API contracts | Zod/Pydantic checks; FastAPI-generated ML schema | Complete Express OpenAPI contract, shared clients and authenticated WebSocket topics remain |
| Cloud | Web/API/ML Container Apps, PostgreSQL, Key Vault, Log Analytics, public GHCR images | Durable model/Parquet storage, scheduled training and worker deployment remain; no new paid services added in this pass |
| Operations/security | Internal API/ML ingress, encrypted broker tokens, single-IP DB firewall, budget notifications | Restore drill, operational alerts, dependency/security review, load tests, incident drills and immutable audit enforcement remain |
| Compliance | Live execution kept disabled, research uncertainty shown | External broker/exchange/data-rights and legal review cannot be certified by implementation work |

## Fixes in this pass

- Broker setup now offers sign-in directly and reads the actual configured callback from the server. The guest page no longer instructs Azure users to use localhost.
- The homepage forwards Dhan root consent returns to the server callback, which still requires the signed, unexpired consent session.
- UI navigation renders immediately while data loads. Session and market requests start independently, requests have timeouts, and Refresh exits the offline state after recovery.
- Nginx compresses JS/CSS/JSON responses. Scale-to-zero settings are retained to avoid silently increasing ongoing costs.
- Feature windows and training labels reset across missing minutes and session boundaries. Invalid OHLCV rows are excluded.
- Both evaluation and calibration use chronological purged splits. Model probability now consistently means positive forward return.
- Inference validates approval and SHA-256 before deserialization, rejects future/timezone-free timestamps, preserves the data timestamp and centers residual intervals on the predicted return.
- Model promotion rejects missing or non-finite validation metrics.
- Candle responses now select the source column before reporting provenance.
- CI requires TypeScript checks, production builds and ML regressions before publishing images.

## Verification

- TypeScript API/web checks: passed.
- API compile and Vite production build: passed.
- Eight ML regression tests: passed. Cover missing minutes, session boundaries, OHLC validity, future-data isolation, chronological label purging, unapproved/tampered artifacts, invalid timestamps and absent-model behavior.
- Test fixtures are synthetic and isolated; no fixture data/model was installed in the application.
- Python dependencies emitted deprecation warnings; tests passed. Dependency pinning and a broader compatibility matrix remain.
- Running Azure endpoints `/`, `/health`, `/api/v1/overview`, `/api/v1/auth/providers`: HTTP 200. Warm timings in this session were 0.22–0.36 seconds; this does not establish cold-start or user-network performance.
- User OAuth, real-history imports, actual model training, paper-fill accounting/replay, backup restore, security and load acceptance are **not yet verified**.

## Operator next steps

1. Sign in to RaGaTrade; Broker setup → Connect Dhan → finish Dhan verification in the same browser.
2. If Dhan returns to the homepage with a token, the updated web app forwards it automatically. Expired/missing consent sessions require starting Connect Dhan again. Do not share token URLs.
3. Verify the connection, import history for multiple equities, export the dataset and review its data rights and quality.
4. Run the documented training CLI; inspect real evaluation results. Human review is required before promotion. A model is not guaranteed to pass those gates.
5. Close the implementation and acceptance gaps in the table before calling the full architecture complete.

Azure IDs, secret names, portal navigation, budget and final revision verification are kept in the local Azure account reference document. Credentials and consent tokens are excluded from this report.

## 3 November 2026 continuation — deployment and real-data findings

Verified after the original report:

- Deployed API and web images from `a32ce990bfce44a6306073bf18d43b57abf40753`. The official Dhan compact security master is synced daily and the API now lists roughly 2,700 NSE EQ stocks with server-side security IDs. Search queries run over that list; the table shows the first 100 results to limit browser work. This does not include BSE, indices or F&O contracts.
- Dhan connection remained active during verification: overview returned `LIVE`; Reliance returned 78 one-minute chart bars with source `DHAN_HISTORICAL`.
- Imported 7,561 validated candles each for nine mapped equities over the allowed 30-day Dhan interval: 68,049 rows total, zero rejected. The operational import script is `infra/db/import-dhan-history.cjs`.
- Exported those real rows locally (ignored `models/`) and trained candidate `lgbm-fd9c6e440ca0` with 49,140 walk-forward evaluation rows over four folds. Candidate failed: Brier 0.250593, worse than random/momentum/logistic references; top-decile gross mean return -0.433 bps before costs. The approval gate refused promotion. Inference intentionally remains `NO_MODEL` / `NO_TRADE`.
- Hourly Azure Container Apps Job `dhan-token-renewal-hourly` was created for supported Dhan Web tokens. It reads only the DB URL and token-encryption key through its managed identity; Key Vault access is secret-get only. It does not renew the existing OAuth token. To use this job, the signed-in RaGaTrade user must enter a current Dhan Web-generated token in Broker setup. The API calls Dhan's renewal endpoint once to validate and replace it; a job renews active Web-origin tokens hourly when under 12 hours remain.
- App broker screen accepts that token in a password field, stores only the encrypted replacement, and does not put tokens in client storage. Current OAuth is labeled as requiring reconnect after expiry. Do not share the token.

Tests since the first report: four Dhan renewal unit tests pass (expiry parsing, encryption round-trip, rejected/invalid and successful mocked renewal); eight Python ML tests pass; API/web TypeScript checks and Vite/API builds pass; CI verification for commit `a32ce99` passed before image publication.

Remaining work includes: user must choose whether to replace OAuth by supplying a Dhan Web token; verify the scheduled job's first real renewal after that setup; finish deployment after the latest instrument filter; import history for the other 2,700 stocks only as explicitly requested and within Dhan limits; BSE/index/F&O support; event/news/macro integrations and rights; an approved model (the current real candidate failed); robust paper OMS and full tests; OpenAPI/WebSocket contracts; backup-restore, security, reliability, compliance and cost acceptance. Live orders remain disabled.
