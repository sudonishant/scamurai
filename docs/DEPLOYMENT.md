# Deployment and operations

Scamurai has three explicit runtime modes. Do not present the local development mode as a production deployment.

| Mode | Database / queue / bytes | Authentication | Intended use |
|---|---|---|---|
| Local | SQLite, in-process jobs, atomic local files | Development role tokens; optional OIDC | Single-machine development and tests |
| Integrated Compose | PostgreSQL, Redis/Celery, MinIO S3 | Development tokens by default | Local integration and disposable CI smoke |
| Production | PostgreSQL, Redis/Celery workers, private S3-compatible storage | Verified OIDC + pre-provisioned users | Controlled deployment after the checklist below |

## 1. Local development

From `backend/`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

From `frontend/`:

```bash
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

`SCAMURAI_REDIS_URL` empty selects the in-process development executor. Setting it selects real Celery dispatch; an unavailable broker is an error, not a fake completed job.

## 2. Integrated Compose stack

The Compose file contains PostgreSQL, Redis, MinIO, an Alembic migration job, FastAPI, a Celery worker and the static UI. The API and worker use non-root images. The default local credentials are development-only and are not production secrets.

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs migration api worker
# UI: http://localhost:5173 ; API: http://localhost:8000
```

The migration job runs before either service starts. The API image healthcheck is liveness only; `/health` reports configured auth/runner/storage modes. The worker overrides that inherited check with Celery `inspect ping`. Actual MinIO write/read and Celery completion are proven by the disposable smoke below, not inferred from liveness.

To stop without deleting data:

```bash
docker compose down
```

`docker compose down -v` permanently deletes the local PostgreSQL and MinIO volumes. Use it only for an intentionally disposable stack.

### Disposable runtime smoke

`backend/scripts/compose_smoke.py` creates a uniquely labelled QA case, uploads a real JSON snapshot and PNG to MinIO, dispatches `media_forensics` through Celery, waits for persisted completion, verifies the saved no-model result, and reads the protected media bytes back byte-for-byte. It is intended for an ephemeral Compose stack, not a production database.

```bash
python backend/scripts/compose_smoke.py
```

GitHub Actions runs this against a newly built stack and then executes `docker compose down -v`. A local Docker daemon is required to reproduce it.

## 3. Database migrations

### Fresh database

```bash
cd backend
alembic upgrade head
alembic check       # models and migration head should agree
```

Production startup does not create or alter schema automatically. Run migrations as a controlled release step before starting the new API/worker version.

### Existing pre-migration development database

Only use the stamp procedure when the existing database schema exactly matches the legacy baseline in `0001_baseline_investigation_schema.py`. Back up first and verify the backup.

```bash
cd backend
cp scamurai_dev.db /secure-backup/scamurai_dev.pre-0002.db
alembic stamp 0001
alembic upgrade head
alembic check
```

Do **not** stamp an unknown or partially migrated schema. Inspect/reconcile it with a database administrator instead. Test copy restoration before touching production.

To test reversibility on a disposable database:

```bash
SCAMURAI_DATABASE_URL=sqlite:////tmp/scamurai-migration-test.db alembic upgrade head
SCAMURAI_DATABASE_URL=sqlite:////tmp/scamurai-migration-test.db alembic downgrade 0001
SCAMURAI_DATABASE_URL=sqlite:////tmp/scamurai-migration-test.db alembic upgrade head
```

A successful downgrade test does not make production downgrades risk-free. Prefer a verified restore for data-preserving rollback.

## 4. Production OIDC

Minimum server configuration:

```dotenv
SCAMURAI_ENVIRONMENT=production
SCAMURAI_DEV_AUTH_ENABLED=false
SCAMURAI_OIDC_ISSUER=https://idp.example.org/
SCAMURAI_OIDC_AUDIENCE=scamurai-api
SCAMURAI_OIDC_JWKS_URL=https://idp.example.org/.well-known/jwks.json
SCAMURAI_OIDC_ALGORITHMS=RS256
SCAMURAI_OIDC_LEEWAY_SECONDS=60
SCAMURAI_OIDC_TIMEOUT_SECONDS=10
SCAMURAI_CORS_ORIGINS=https://ui.example.org
```

The API validates the token signature, allowed algorithm, issuer, audience, expiry, issued-at time and required `iss/aud/sub/exp/iat` claims. JWKS clients are cached so normal requests do not reconstruct the key service client. Key rotation remains handled by PyJWT's JWKS cache.

A valid external identity still receives no Scamurai access until explicitly provisioned:

```bash
cd backend
python scripts/provision_oidc_user.py \
  --issuer 'https://idp.example.org/' \
  --subject 'stable-idp-subject-claim' \
  --email 'analyst@example.org' \
  --name 'Authorized Analyst'
```

To grant an initial case role in the same operation:

```bash
python scripts/provision_oidc_user.py \
  --issuer 'https://idp.example.org/' \
  --subject 'stable-idp-subject-claim' \
  --email 'reviewer@example.org' \
  --case-id 'existing-case-uuid' \
  --role reviewer
```

Use the IdP's stable `sub`, not an email address, as `auth_subject`. Email/name changes do not replace the external identity key. Production `/users` returns only the current non-secret identity.

**Browser boundary:** the React client currently accepts an OIDC bearer access token directly. Interactive OIDC Authorization Code + PKCE, refresh-token rotation and a backend-for-frontend cookie session are not implemented. Before a public rollout, provide a trusted token flow or session gateway; do not ask users to exchange long-lived tokens through chat or put client secrets in frontend variables.

## 5. PostgreSQL, Celery and object storage

Production examples (place secret values in a secret manager, not this file):

```dotenv
SCAMURAI_DATABASE_URL=postgresql+psycopg://scamurai:PASSWORD@postgres:5432/scamurai
SCAMURAI_REDIS_URL=redis://redis:6379/0
SCAMURAI_STORAGE_BACKEND=s3
SCAMURAI_S3_BUCKET=private-case-evidence
SCAMURAI_S3_REGION=us-east-1
SCAMURAI_S3_ENDPOINT=
SCAMURAI_S3_FORCE_PATH_STYLE=false
```

For MinIO or another S3-compatible service, set its HTTPS `SCAMURAI_S3_ENDPOINT` and usually `SCAMURAI_S3_FORCE_PATH_STYLE=true`. Prefer workload/IAM credentials; if static credentials are unavoidable, use `SCAMURAI_S3_ACCESS_KEY` and `SCAMURAI_S3_SECRET_KEY` only in the server/worker secret store.

Run at least one worker with the same database, storage and provider configuration as the API:

```bash
celery -A worker.celery_app worker --loglevel=INFO --queues=scamurai
```

Persisted jobs dispatch as `scamurai.execute_job`. Late acknowledgement gives at-least-once execution, not exactly-once delivery; handlers rely on idempotency and unique constraints. Test worker termination, broker restart and requeue behavior under the actual deployment configuration.

S3 buckets must be private with least-privilege read/write access. Configure encryption, retention/lifecycle, backup and deletion policies externally; an expiring export URL does not replace bucket policy.

## 6. Static Pages UI + separate API

GitHub Pages hosts only the React static files. It does not run FastAPI, Celery, PostgreSQL or scheduled OSINT collection.

1. Deploy and migrate the API/worker stack separately with HTTPS.
2. Set the non-secret Actions variable `SCAMURAI_PUBLIC_API_URL` to the API base URL, or enter it on the sign-in screen.
3. Add the exact UI origin (without a path) to `SCAMURAI_CORS_ORIGINS`.
4. Never put PATs, provider keys or bearer tokens in `VITE_*`, Actions variables, static files or Git remote URLs.

The build includes `frontend/public/404.html`. On Pages, missing path-style case/account/post/alert/evidence links recover to canonical query deep links; unknown routes show an honest workspace not-found page. Its `BASE` is `/scamurai/` and must be changed if the deployed repository path changes. Production-emulation tests serve the actual `dist/` files and 404 responses, not Vite's development fallback.

The included workflow deploys Pages only after backend tests, migration checks, dependency/security scans, frontend build and Chromium E2E pass on `main`; the real Compose smoke is also required.

## 7. Release checklist

- [ ] Review the exact migration on a production-like copy; verify backup and restoration.
- [ ] Production environment set; development tokens disabled; OIDC and explicit users tested.
- [ ] Safe browser token/session flow, TLS, exact CORS, gateway rate limits and security headers configured.
- [ ] PostgreSQL/Redis/Celery/S3 health and worker recovery tested; secrets held in a secret manager.
- [ ] Network egress policy blocks non-public destinations; SSRF redirect/rebinding tests reflect the real network.
- [ ] Privacy, retention, legal authorization, source terms and incident-response procedures reviewed.
- [ ] Full backend/frontend/E2E/security checks and disposable Compose smoke pass.
- [ ] Model and heuristic metrics are reported as uncalibrated unless representative evaluation establishes otherwise.
