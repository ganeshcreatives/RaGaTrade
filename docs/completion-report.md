# RaGaTrade implementation and verification report

Date: 17 November 2026 (India time)
Reference: `ai_trading_architecture.html`. This is an implementation inventory, not a production readiness certificate.

## Overall result

The development application is deployed and the Dhan read-only connection is verified,
but the full architecture is **not complete**. No reviewed production model artifact has
been installed. Missing licensed data remains unavailable; models return NO_TRADE.

## Architecture coverage

| Area | Implemented | Remaining and reason |
|---|---|---|
| Frontend | React dashboard, instruments, watchlist, paper portfolio, alerts, research, broker setup | Comprehensive browser/mobile/accessibility acceptance testing remains |
| Identity | Email/password login, hashed passwords, server sessions, user-scoped routes; Google adapter | Email verification, password recovery, MFA and Google provider configuration are not complete |
| Backend/data | Express, PostgreSQL schema, persisted accounts/orders/ledger/audit; request validation | Migration tooling, broad contract coverage and stronger operational controls remain |
| Dhan connection | Verified Dhan Web token stored encrypted; profile verification, hourly renewal job, read-only polling | Verify scheduled token rotation at runtime; renewal can fail on revocation or outage |
| Market quotes | Official NSE EQ instrument master and read-only quote polling; 2,756 of 2,756 catalogued equities returned live Dhan quotes at verification | No Dhan WebSocket, order-book depth, exchange timestamps or licensed index feed |
| History | Dhan one-minute import with OHLCV validation, database persistence, CSV export and incremental sync when AI Research opens | Corporate-action adjustment, exchange calendar, gap reconciliation and archive pipeline remain |
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

## 17 November 2026 follow-up — auto-sync and renewal job

- AI Research now requests an incremental Dhan history sync automatically when a signed-in user selects an equity with no candles or candles older than 36 hours. The deployed interface labels the manual action **Sync selected equity now**. It never turns fabricated/sample bars into training data.
- Web revision `web--0000008` and API revision `api--0000012` are healthy. `/health` returns HTTP 200 with PostgreSQL connected. A synthetic invalid-credential login probe returns the expected HTTP 401 in about 0.5 seconds; this does not verify any real account password.
- The hourly `dhan-token-renewal-hourly` job was failing because its identity lacked Key Vault `get`, and its container environment did not bind both secret references. After the user approved vault-wide `get` for this identity, the job was reconfigured and a manual execution completed with exit code 0. The hourly schedule remains `15 * * * *`. This verifies job startup and database access, but not token renewal.
- Dhan’s profile showed the Data APIs plan active at ₹499 + GST/month. The live app API still reported no unexpired Dhan token and zero live quotes. Dhan Web access tokens are valid for 24 hours; the renewal endpoint only renews active Web-generated tokens. The already-used OAuth connection will not be renewed by this job. A current Web-generated token must be connected through Broker setup before actual renewals or real imports can be verified.
- The Dhan connection/access-token step is pending. The user was asked whether to issue a new Web token and replace the OAuth connection; do not create or rotate it without that action-time approval. Keep all token values out of chat and logs.
- Verification: `npm run typecheck`, `npm run build`, and four API renewal unit tests passed locally. The local ML unittest command could not import `numpy`; GitHub Actions for commit `0dce984` completed the configured verify and API/web/ML image-publish jobs successfully.
- Production readiness remains incomplete: no active Dhan token or live quotes, no point-in-time licensed model dataset, no approved model (candidate failed its gates), no licensed news/index/global-event sources, no cloud model artifact registry or training schedule, and restore/load/security/compliance acceptance remain outstanding. Live order execution remains disabled.

## 17 November 2026 follow-up — verified live connection and cleanup

This section supersedes the earlier 17 November status above where it says the Dhan connection is pending or no live quotes are available.

- Signed into the RaGaTrade application, connected a fresh Dhan Web token through the corrected encrypted token endpoint, and verified the account against Dhan Profile. The overview returned a live Reliance quote with `DHAN_API` provenance.
- The deployed API initially reported 2,760 entries, of which 2,756 had live Dhan quotes and four were unavailable (the index and Dhan test scripts). After the filter and overview fix were deployed, the live endpoint reported 2,756 entries, all 2,756 with `DHAN_API` source, zero unavailable or synthetic-source rows, and no index/test symbols. The overview quote count also reported 2,756.
- Removed the unused Redis demo market worker and placeholder trading worker from the local Compose stack and repository. The API now serves historical chart, export, and backtest rows only when their source is verified Dhan history; legacy non-Dhan bars are rejected from use.
- Automatic incremental history sync is described in the UI and runs when a signed-in user opens AI Research for an equity with missing or stale candles. History import still depends on Dhan's account limits and data-use rights.
- Checks on this source revision: TypeScript typechecks and API/web production builds passed; 7 API token tests and 8 ML research tests passed. Python emits a Starlette/httpx deprecation warning and NumPy timedelta deprecation warnings; these do not fail tests.
- Commit `6fc1e32c82f5cd638b31e484f91e87f1df923878` passed the GitHub Actions verification and API/web/ML image builds. Azure now runs API revision `api--0000014` and web revision `web--0000009`; `/health` reports `ok` with PostgreSQL connected. Live feed status was `LIVE`, and Reliance was sourced from `DHAN_API`.
- The current real-data LightGBM candidate did not pass the evaluation gate, so forecasts stay unavailable/`NO_TRADE`. No fabricated values or model outputs are substituted.

Remaining gates include observing an actual scheduled token rotation, licensing rights for any redistribution, index/news/event providers, full-history coverage, a passing reviewed model, durable model registry/training, operational restore/load/security acceptance, and legal/regulatory review. Live trading remains disabled. Do not describe this build as production-ready for unattended or live trading.

## 17 November 2026 follow-up — full-universe history queue

- Added a user-scoped background job to queue real Dhan one-minute history for every active mapped NSE equity. It is opt-in from AI Research, accepts 1–90 calendar days (30 by default), records per-symbol outcomes in PostgreSQL, retries transient errors, resumes stale in-progress work after restart, and reports total/completed/failed/pending/current-symbol progress.
- A PostgreSQL advisory lock prevents duplicate queue workers across API replicas. The worker handles one request at a time at a conservative cadence below Dhan's published 5 requests/second and 100,000 Data API requests/day limits. Dhan allows up to 90 days per intraday history request. A full catalogue download may take many minutes and consume substantial database storage.
- This queues history only. It does not create a model, score every stock, or approve a candidate. The currently installed production state still has no approved model because the last real-data candidate failed evaluation. The scorer continues to suppress forecasts until a real candidate passes independent validation and named human approval.
- Verification on this source tree: API/web typechecks and production build passed; 7 API tests and 8 ML tests passed; `git diff --check` passed. The API integration path still needs a live Azure job run and Dhan batch response verification before claiming successful full-catalogue coverage.
- Commit `7dba8576e12f0f82c67990a8941c73c4348905a5` passed GitHub Actions and published all images. Azure API revision `api--0000016` and web revision `web--0000012` now run that commit. Verified web `/` and the new JS asset return HTTP 200, API `/health` reports PostgreSQL connected, and the private history-job status route correctly returns 401 without a session. No full-catalogue job was started.
- The post-deploy `/api/v1/overview` listed all 2,756 mapped equities, but quote feed status was `OFFLINE` with zero cached quotes at 22:51 India time, outside NSE regular trading hours and just after the API revision restart. This is not a live-market quote verification; recheck during market hours before claiming current Dhan feed is live.
