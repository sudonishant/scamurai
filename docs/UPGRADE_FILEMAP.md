# Investigation-operations upgrade — exact file map

This is the file-level index for the roadmap implementation. The repository source is authoritative; the final release also has a `git format-patch` artifact for an exact byte-level patch. No demo evidence, synthetic live fallback or hidden provider capability is introduced.

## Runtime, dependencies and deployment

| File | Exact change |
|---|---|
| `.env.example` | Documents local/S3 storage, OIDC/JWKS, dev-auth enforcement and aggregate-geo threshold settings without secrets. |
| `docker-compose.yml` | Adds runnable PostgreSQL, Redis, MinIO, migration, API, Celery worker and frontend topology with health dependencies and service-specific migration/API/worker healthchecks; uses digest-pinned public Chainguard MinIO server/client builds after upstream image withdrawal. |
| `backend/Dockerfile` | Uses runtime requirements, non-root execution and the production API entrypoint. |
| `frontend/Dockerfile` | Uses strict locked installation before the static build. |
| `backend/requirements.txt` | Declares Alembic, PostgreSQL, Redis/Celery, Boto3, JWT/cryptography and the SciPy runtime required by NetworkX PageRank; no reliance on incidental local packages. |
| `backend/requirements-dev.txt` | Separates pytest, Bandit and pip-audit development/security tooling. |
| `Makefile` | Adds migration/security targets, locked frontend install and both evaluation harnesses. |
| `.github/workflows/deploy.yml` | Gates Pages on backend tests, migration reversibility, multilingual/notebook checks, Bandit, pip-audit, npm audit/build, Chromium E2E/accessibility and real Compose smoke. |

## Authentication, schema and migrations

| File | Exact change |
|---|---|
| `backend/app/config.py` | Adds fail-closed production/dev-auth validation, OIDC settings, S3 configuration and minimum geo group-size validation. |
| `backend/app/security.py` | Implements verified OIDC issuer/audience/signature/expiry/required-claim handling, pre-provisioned identity mapping, cached JWKS clients and production-safe user behavior while retaining RBAC/SSRF defenses. |
| `backend/app/main.py` | Adds production startup guards, new routers and non-secret infrastructure/auth health reporting. |
| `backend/app/models.py` | Adds external identity fields, persistent alerts/review fields and post/account provenance timestamps. |
| `backend/alembic/versions/0001_baseline_investigation_schema.py` | Captures the reviewed legacy schema as a repeatable baseline with downgrade support. |
| `backend/alembic/versions/0002_oidc_alerts_and_provenance.py` | Adds OIDC/provenance/alert schema changes with SQLite batch-compatible constraints and provenance backfill. |
| `backend/scripts/provision_oidc_user.py` | Adds explicit issuer+subject user and optional case-membership provisioning; no self-registration or role inference. |

## Durable jobs, storage and ingestion

| File | Exact change |
|---|---|
| `backend/app/services/jobs.py` | Dispatches persisted jobs by registered Celery task name when Redis is configured; retains explicit local execution otherwise. |
| `backend/app/services/tasks.py` | Executes persisted job kinds through the shared service registry with idempotent completion behavior. |
| `backend/worker.py` | Configures the real Celery application, queue, late acknowledgement and registered task. |
| `backend/app/routers/runs.py` | Routes run creation through the shared persisted-job dispatcher instead of a separate fake path. |
| `backend/app/routers/agent.py` | Routes bounded-agent execution through the same real job dispatcher. |
| `backend/app/services/storage.py` | Implements atomic local writes and real S3/MinIO `put_object`/`get_object`, stream closing and honest path limitations. |
| `backend/app/routers/cases.py` | Handles identical upload replay honestly and preserves existing-input response semantics. |
| `backend/app/schemas.py` | Exposes the input `replayed` flag so replay is visible rather than disguised as new collection. |
| `backend/app/services/importer.py` | Normalizes distinct source/first-seen/collection provenance without inventing publication timestamps. |

## Investigation intelligence and APIs

| File | Exact change |
|---|---|
| `backend/app/services/analytics.py` | Adds persistent-alert reconciliation inputs, evidence-completeness scoring, separate fact/hypothesis graph metrics, Louvain/bridge candidates, geo k-suppression, normalized provenance and Unicode combining-mark-safe tokenization. |
| `backend/app/services/textutil.py` | Preserves Unicode letters/numbers and combining marks during NFKC/case-fold punctuation normalization, fixing Devanagari corruption. |
| `backend/app/services/alerts.py` | Reconciles durable active/inactive alerts and applies audited analyst review state without resetting decisions on refresh. |
| `backend/app/routers/alerts.py` | Adds case-scoped alert history and reviewer/owner status, priority and note endpoints. |
| `backend/app/routers/accounts.py` | Adds bounded account inventory/detail APIs with exact evidence, shared URLs, behavior indicators and provenance. |
| `backend/app/routers/search.py` | Adds bounded grouped search over case accounts, posts, findings, alerts and evidence; no cross-case read-all search. |

## React investigation workspace

| File | Exact change |
|---|---|
| `frontend/src/App.tsx` | Restores case/tab/entity state from URLs and synchronizes history/deep-link navigation. |
| `frontend/src/components/Workspace.tsx` | Integrates Alerts, Accounts, global search, focused navigation, unresolved-cue indicators and entity drill-down. |
| `frontend/src/components/GlobalSearch.tsx` | Adds debounced grouped case search, result states and keyboard-focusable destination buttons with valid input semantics. |
| `frontend/src/components/AlertsView.tsx` | Adds persistent alert history, evidence method, analyst notes/review controls and deep-link loading-race protection. |
| `frontend/src/components/AccountsView.tsx` | Adds account/post evidence drill-down, source/first-seen/collection timestamps and shared URL/behavior context. |
| `frontend/src/components/OverviewView.tsx` | Links unresolved cues into durable alert review while retaining coverage and data-gap states. |
| `frontend/src/components/NarrativesView.tsx` | Adds post focus and separate publication/first-seen/collection provenance without originator claims. |
| `frontend/src/components/NetworkView.tsx` | Displays structural metrics/communities/bridge limitations and makes the interactive SVG an accessible group. |
| `frontend/src/components/GeoView.tsx` | Displays privacy suppression/coverage and approximate aggregate location semantics. |
| `frontend/src/components/FindingsView.tsx` | Supports focused finding deep links and review navigation. |
| `frontend/src/components/ConnectorsView.tsx` | Completes ARIA table header/cell roles and labels the source-health refresh button. |
| `frontend/src/components/OsintView.tsx` | Labels the icon-only report-history refresh control. |
| `frontend/src/components/StartScreen.tsx` | Labels the new-case modal close control. |
| `frontend/src/components/UploadBar.tsx` | Labels the collection-panel close control. |
| `frontend/src/lib/api.ts` | Adds typed account, alert-review and search requests. |
| `frontend/src/lib/types.ts` | Adds DTOs for provenance, alerts/review, accounts, search, graph metrics and geo privacy. |
| `frontend/src/index.css` | Adds responsive investigation-operations layouts/deep-link focus styles and raises muted-text contrast while retaining the neon theme. |

## Regression tests and evaluation

| File | Exact change |
|---|---|
| `backend/tests/test_investigation_operations.py` | Covers production auth fail-closed behavior, signed OIDC claims/provisioning/JWKS reuse, Celery dispatch, S3 bytes, persistent alert review, geo privacy, provenance and upload replay. |
| `backend/tests/test_multilingual_evaluation.py` | Locks Devanagari mark preservation/tokenization and the diagnostic's honest no-semantic-model contract. |
| `backend/fixtures/multilingual_narratives.json` | Adds 14 explicitly synthetic same-language, cross-lingual and different-narrative control pairs. |
| `backend/scripts/evaluate_multilingual.py` | Computes reproducible lexical pair metrics by track, retains false candidates and labels semantic scores unavailable rather than zero. |
| `backend/scripts/compose_smoke.py` | Verifies real disposable Compose health, MinIO snapshot/media upload and byte-for-byte readback, persisted no-model forensics and Celery completion. |
| `frontend/e2e/smoke.spec.ts` | Provides eight browser tests covering account/post deep links, durable alert review and all-impact axe WCAG scans with JSON artifacts. |
| `frontend/e2e/pages.spec.ts` | Emulates production GitHub Pages file/404 responses and verifies nested case/entity route recovery, query preservation, assets and honest unknown routes. |
| `frontend/public/404.html` | Recovers path-style case/evidence links to canonical query deep links and provides a safe neon branded unknown-route page without substituting evidence. |
| `frontend/package.json` | Adds `@axe-core/playwright` as a development-only accessibility test dependency. |
| `frontend/package-lock.json` | Locks the accessibility dependency graph; production runtime dependencies are unchanged by this addition. |
| `notebooks/multilingual_semantic_evaluation.ipynb` | Adds an output-free optional public-model pairwise evaluation experiment with blank model/revision and no inherited lexical threshold. |
| `notebooks/README.md` | Restricts Colab/Jupyter use to non-sensitive evaluation and documents official API/runtime boundaries. |

## Documentation

| File | Exact change |
|---|---|
| `README.md` | Updates real capabilities, API/access matrix, OIDC/storage/Celery quickstart, investigation navigation, Pages route recovery and ten-test verification instructions. |
| `docs/USAGE.md` | Aligns Hinglish workflows with persistent Alerts, Accounts, search/deep links, migrations and current limitations. |
| `docs/SECURITY.md` | Documents verified OIDC/provisioning, cached JWKS, private S3/local storage, geo suppression, Celery delivery semantics and deployment controls. |
| `docs/INTELLIGENCE.md` | Documents Unicode handling, graph algorithms, persistent review cues, evidence-completeness formula, geo privacy and provenance semantics. |
| `docs/DEPLOYMENT.md` | Adds exact local/Compose/production commands, backup/stamp/migrate procedure, OIDC provisioning, S3/Celery operations and release checklist. |
| `docs/VALIDATION.md` | Records measured test/migration/security/accessibility/evaluation results and unverified operational boundaries without accuracy claims. |
| `docs/UPGRADE_FILEMAP.md` | Provides this complete file-level index for the exact implementation patch. |
