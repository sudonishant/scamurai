# Scamurai — evidence-first coordinated-disinformation investigation

Scamurai is a FastAPI + React workspace for authorized analysts who need to collect public-source evidence, examine narrative propagation, review possible coordination, inspect media, and preserve a defensible audit trail.

It is deliberately **an investigation tool, not an accusation engine**:

- **Established observations** are separated from similarities, hypotheses, and unknowns.
- “Earliest observed” means earliest **inside the collected case corpus**, not platform-wide origin.
- A timing or repetition score is not a bot probability, maliciousness score, or common-ownership finding.
- A missing API result, inaccessible post, absent metadata field, or empty fact-check response is not proof that something does not exist.
- The product runtime is **live-only**. Authentication, provider, and transport failures remain visible; they never activate synthetic evidence or an offline demo. Synthetic fixtures are confined to automated tests and evaluation.

## Implemented capabilities

| Area | What is real in this repository | Important boundary |
|---|---|---|
| Case investigation | Case-scoped RBAC, evidence records, typed graph, review workflow, audit events, exports | Development tokens must be replaced before deployment |
| Authorized imports | Public URL/text intake; JSON/CSV/signature-checked image upload; raw snapshots and hashes | Import authorization and platform terms remain the operator’s responsibility |
| Public social source | Bounded Mastodon public-hashtag collection through the selected instance’s official API | One page, no private/unlisted statuses; instances may disable public preview |
| YouTube and fact checks | Official YouTube commentThreads and Google Fact Check adapters | Require server-side API keys; quota/access failures remain visible |
| Public-infrastructure OSINT | DNS-over-HTTPS, IANA-bootstrapped RDAP, bounded web metadata, crt.sh CT observations, Wayback availability | Passive/bounded research only; no scanning, breach lookup, login bypass, or private identity resolution |
| Narratives | TF-IDF/cosine similarity clusters, representative posts, timelines, observed propagation order, cross-account similarity | Similarity is not proof of orchestration; clustering input is bounded |
| Account behavior | Transparent duplicate-text, timing, regularity, and posting-rate indicators with evidence coverage | Explicitly **not calibrated bot probability** |
| Network analysis | Account links derived from the evidence graph, fact/hypothesis edge separation, observed connected components | No inferred shared identity or intent |
| Geospatial analysis | Aggregated points from supplied metadata/authorized imports, timelines, baseline/anomaly review cues | Not live device tracking; missing location data is a coverage limitation |
| Early warnings | Explainable narrative-acceleration and geo-spike attention rules with evidence IDs and recommended review action | Attention scores are triage rules, not threat probabilities |
| Media screening | SHA-256, pHash, selected metadata, possible provenance-marker bytes, bounded pixel/JPEG residual measurements | C2PA byte markers are not cryptographic validation; residuals are not manipulation verdicts |
| Optional synthetic-image model | A configured local Hugging Face image classifier can return raw labels and an uncalibrated label-aggregation score | No score when no model is configured; model/threshold validation is still required |
| Existing analysis pipelines | Image matching, comments, coordination candidates, claims, metadata-first location findings, bounded agent, jobs and exports | See method notes and per-result limitations |

### Not claimed or silently simulated

- There is **no platform-wide firehose or continuous real-time monitor**. Analytics are computed on demand from the currently collected case corpus.
- There is no built-in deterministic deepfake verdict or calibrated bot/deepfake confidence.
- Video/deepfake analysis is not implemented merely by running an image classifier. Unsupported media remains unsupported.
- Instagram/Facebook private or restricted content, Reddit approval-gated access, OCR, and reverse image search are not represented as working when unconfigured.
- Content Credentials/provenance and content-based synthetic-media detection answer different questions. Absence of either is not evidence of authenticity or manipulation.

## API and access requirements

The same matrix appears in the workspace under **Connectors**. “No API key” does not mean unrestricted access or unlimited redistribution.

| Capability | Access | Actual behavior |
|---|---|---|
| Authorized JSON, CSV, text and image imports | **No API key** | User-supplied authorized evidence, not live platform collection |
| DNS, RDAP, web metadata, CT and Wayback | **No API key** | Real bounded public requests; availability and rate limits still apply |
| Mastodon public hashtag timelines | **Keyless if permitted** | Official instance API, one public page when public preview is allowed |
| Narratives, network, geo and early warnings | **No API key** | Local analysis of the current case corpus, not a platform firehose |
| Hashes, metadata and pixel screening | **No API key** | Deterministic local observations, no standalone manipulation verdict |
| YouTube public comments and replies | **API key required** | `SCAMURAI_YOUTUBE_API_KEY`; official Data API v3 access and quota |
| Published Google fact-check search | **API key required** | `SCAMURAI_GOOGLE_FACTCHECK_API_KEY`; no match never proves falsity |
| External LLM for the bounded agent | **Optional API key** | Local deterministic tools need no LLM; Groq/Gemini/OpenRouter need credentials |
| Synthetic-image classifier | **Local model** | Configure a Hugging Face model and optional dependencies; output is uncalibrated |
| Instagram, Facebook and Reddit | **Official access** | Reviewed OAuth/permissions or approval required; no unconfigured live success |
| OCR, reverse image search and video deepfakes | **Not available** | No working configured pipeline; no substitute result is generated |

## Investigation UI

The black/neon-green/JetBrains Mono interface uses [osint-ui.com](https://osint-ui.com/en) solely as its visual reference. Scamurai retains its own coordinated-disinformation workflows; unrelated reference-site tools are not included.

- **Overview:** evidence coverage, data gaps, priority review cues, and narrative pulse.
- **Narratives:** timelines, representative evidence, propagation order, and explainable acceleration rules.
- **Geospatial:** an offline bundled Natural Earth map plus aggregate location tables—no external map-tile tracking.
- **Live OSINT:** selectable source modules, per-source success/empty/limited/failed states, report history, raw evidence, and JSON export.
- **Network & behavior:** observed account graph and transparent automation indicators.
- **Media lab:** authorized media previews, integrity/metadata/pixel observations, model availability, and limitations.
- **Evidence tools:** typed graph, entity explorer, comments, findings review, account comparison, exports, connectors, and bounded agent.
- Responsive layouts, visible loading/empty/error states, role-aware controls, bundled fonts, and reduced-motion support.

## Quickstart

Requirements: **Python 3.13+** and **Node.js `^20.19` or `>=22.12`** (Vite 8 requirement). No database server or API key is needed for local authorized imports and deterministic analysis.

```bash
# Backend — terminal 1
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend — terminal 2
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

Open `http://localhost:5173`. FastAPI Swagger is at `http://localhost:8000/docs`.

For the fixed local development roles below, run `cp .env.example backend/.env` from the repository root before starting the backend. The sample file explicitly enables `SCAMURAI_DEV_AUTH_ENABLED`; the application default is off, and the fixed development tokens must not be enabled on a public deployment.

Convenience targets:

```bash
make install
make db-upgrade   # apply schema revisions before the first local API start
make run-api       # terminal 1
make run-web       # terminal 2
```

Docker Compose remains available for the PostgreSQL/Redis/MinIO development stack:

```bash
cp .env.example .env
docker compose up --build
```

Compose runs the one-shot Alembic migration service before starting the API and worker.
For upgrading existing databases safely, see [`docs/DATABASE_MIGRATIONS.md`](docs/DATABASE_MIGRATIONS.md).

### Development roles

| Role | Token | Intended access |
|---|---|---|
| Owner | `dev-token-owner` | Case administration, collection, analysis, review, export |
| Analyst | `dev-token-analyst` | Collection and analysis workflows |
| Reviewer | `dev-token-reviewer` | Findings review |
| Viewer | `dev-token-viewer` | Read-only access to cases shared with that user |

Paste either the token itself or the full `Bearer dev-token-owner` value; the client normalizes it. These are local development conveniences, **not production authentication**.

### Live session behavior

- **Open live workspace** validates the token by calling the real cases API. Failures stay on screen.
- There is no demo button, demo route, synthetic fallback, or fabricated “offline result.”
- Logout clears only Scamurai’s session keys, not unrelated browser storage.
- The default API address is same-origin; Vite proxies `/api` to FastAPI. A remote API can be configured before login or from the top bar when CORS permits it.
- A 401 ends the stale workspace session and returns to sign-in with an explicit message while preserving the configured backend URL.

### GitHub Pages frontend + separately deployed API

GitHub Pages can host the static UI, but it cannot run FastAPI or OSINT workers. The included workflow never substitutes demo data when no backend is configured.

1. Deploy FastAPI separately with durable storage/workers appropriate for the environment.
2. In the repository's GitHub Actions variables, optionally set the **non-secret** `SCAMURAI_PUBLIC_API_URL` to the public FastAPI base URL. The workflow exposes it as `VITE_API_BASE_URL` at build time. Users can instead enter it under **Live API connection** on the sign-in screen.
3. Add the exact UI origin—not the `/scamurai/` path—to backend CORS, for example:
   ```dotenv
   SCAMURAI_CORS_ORIGINS=https://neeshant.is-a.dev,http://localhost:5173,http://127.0.0.1:5173
   ```
4. Keep provider credentials and bearer/PAT tokens out of Actions variables, frontend code, static artifacts, Git history, and remote URLs. Any `VITE_*` value is public in the built JavaScript.

A public backend also needs production authentication, TLS, CORS restrictions, and the deployment controls in [`docs/SECURITY.md`](docs/SECURITY.md). Development tokens are not a safe public authentication solution.

## Optional configuration

Settings use the `SCAMURAI_` prefix. See `.env.example` and [`docs/REQUIRED_CREDENTIALS.md`](docs/REQUIRED_CREDENTIALS.md).

```dotenv
SCAMURAI_DEEPFAKE_MODEL_ID=
SCAMURAI_DEEPFAKE_MODEL_REVISION=
SCAMURAI_OSINT_TIMEOUT_SECONDS=12
SCAMURAI_OSINT_MAX_HOSTNAMES=150
SCAMURAI_YOUTUBE_API_KEY=
SCAMURAI_GOOGLE_FACTCHECK_API_KEY=
SCAMURAI_LLM_PROVIDER=
SCAMURAI_LLM_MODEL_ID=
SCAMURAI_LLM_API_KEY=
SCAMURAI_LLM_BASE_URL=
SCAMURAI_GEMINI_API_KEY=
```

A Hugging Face model also requires the optional `transformers`/`torch` dependencies. Review the exact model card and measure performance on representative, unseen-generator and compressed local data before operational use. Provider pricing, free tiers, quotas, and approval policies can change; verify them in the linked official documentation rather than treating this repository as a guarantee.

## Analytics and evidence semantics

- Narrative clustering uses normalized lexical TF-IDF vectors and cosine similarity over at most 500 collected posts. The response reports whether the input was truncated.
- Timelines use hour/day/week buckets according to the observed span and preserve undated-item counts.
- Acceleration compares the latest bucket with the preceding three buckets. Its attention score and rule inputs are returned with evidence IDs.
- Automation indicators expose the raw feature values, triggered rules, formula, timestamp coverage, and limitations. They are not “percent bot” values.
- Geospatial points are rounded aggregates for display. They describe supplied/reported location observations, not a person’s current position.
- Media integrity and screening observations remain separate from optional model output.
- Every OSINT report is stored as a hash-manifested evidence snapshot with independent module outcomes.

See [`docs/INTELLIGENCE.md`](docs/INTELLIGENCE.md) for method details and official source references.

## Main API additions

All case routes require a bearer token and case membership.

| Route | Purpose |
|---|---|
| `GET /api/v1/cases/{id}/analytics` | Narratives, behavior, network, geospatial coverage, and review alerts |
| `POST /api/v1/cases/{id}/osint/investigate` | Bounded public-source investigation |
| `GET /api/v1/cases/{id}/osint/reports` | Saved report history |
| `GET /api/v1/cases/{id}/osint/reports/{report_id}` | Full source-attributed report |
| `GET …/reports/{report_id}/download` | Canonical JSON with `X-Content-SHA256` |
| `POST /api/v1/cases/{id}/connectors/mastodon/import` | Bounded public-hashtag collection |
| `POST /api/v1/cases/{id}/runs` with `workflow=media_forensics` | Queue media screening |
| `GET /api/v1/cases/{id}/media/forensics` | Saved observations and optional model output |

Existing case, input, graph, comment, claim, review, export, agent, and provider routes remain under `/api/v1`.

## Verification

```bash
# Hermetic backend suite (provider HTTP is mocked)
cd backend && python -m pytest tests/ -q

# Production frontend build and dependency audit
cd frontend && npm ci && npm run build && npm audit --audit-level=moderate

# Browser tests: start API :8000 and Vite :5173 first
npx playwright install chromium
npm run test:e2e

# Optional isolated QA fixtures and metric harness; not investigation input
make fixtures
make eval
```

The Playwright suite creates its own clearly labelled validation case through the real API, so it needs neither a pre-seeded database nor an external provider. Its five checks cover real findings review, bearer-token normalization, API/access requirements, mobile overflow, hosted remote-API configuration and 401 handling, and the rule that a live transport failure must not substitute demo evidence.

The latest point-in-time results and external-source connectivity checks are recorded in [`docs/VALIDATION.md`](docs/VALIDATION.md). Connectivity is not an accuracy benchmark.

## Security and deployment boundaries

- URL fetches use scheme/credential checks, non-global IP rejection, bounded responses/timeouts, and per-redirect validation.
- Validation-time DNS checks do not by themselves eliminate DNS-rebinding/TOCTOU risk. Internet-facing multi-tenant deployment still needs network egress policy and, where feasible, connection-level DNS pinning.
- Uploaded images are checked by signature, size, and decode limits. Protected media previews use authenticated blob retrieval.
- Provider content is untrusted data, not agent instructions. Keys remain server-side.
- Replace dev tokens, configure TLS/IdP/PostgreSQL/durable workers/private object storage, and complete jurisdiction-specific privacy, retention, and evidence-handling review before deployment.

More detail: [`docs/SECURITY.md`](docs/SECURITY.md), [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md), and [`docs/USAGE.md`](docs/USAGE.md).

## Project map

```text
backend/app/
  routers/       cases, runs, graph, comments, connectors, osint, analytics, media, exports, agent
  services/      evidence pipelines, analytics, OSINT, media screening, providers, jobs, exports
  models.py      case-scoped evidence, source access, graph, reports and forensic records
  config.py      SCAMURAI_-prefixed runtime settings
backend/tests/   acceptance, security, provider, intelligence and configuration tests
frontend/src/
  components/    mission dashboards, source workbench, graph/evidence and review views
  lib/           typed live-only API client and shared types
frontend/e2e/    self-contained Playwright browser checks with isolated validation fixtures
docs/            architecture, usage, integrations, intelligence methods, security, validation
```

## Human-review reminder

Shared wording can result from breaking news, press releases, hashtags, quoted material, or ordinary audience behavior. Location metadata can be wrong or spoofed. Registry data does not establish website intent. A model label can be wrong. Scamurai preserves these caveats beside the evidence so an analyst can investigate alternatives rather than mistake a screening cue for a conclusion.
