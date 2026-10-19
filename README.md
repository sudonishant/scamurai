# Scamurai — Social Media Coordinated Disinformation Detection System

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)
![React](https://img.shields.io/badge/React-19-61dafb)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6)
![Tests](https://img.shields.io/badge/tests-49%20passing-2ea44f)
![Status](https://img.shields.io/badge/status-Milestone%201%20complete-success)

A browser-based, **evidence-first** Maltego-style investigation workspace. An authorized
analyst submits post URLs, public account references, images, text claims, and authorized
comment exports; the system preserves evidence, finds related content, detects patterns
consistent with possible coordination, assesses claims, and explains every conclusion on
an interactive **typed graph** with exportable, hash-manifested reports.

The product is deliberately **an investigation tool, not an accusation engine**. Every
output separates:

1. **What is established** — source-supported facts (`fact` edges, solid green)
2. **What is a signal/hypothesis** — algorithmic similarity, review candidates (`similarity` / `hypothesis` edges, dashed/dotted)
3. **What remains unknown** — insufficient evidence, inaccessible sources (never silently filled)

> Shared content is never proof of common account ownership.
> Coordination is never automatically malicious.
> An inaccurate claim never establishes deliberate deception.

---

## Table of contents

- [Feature matrix](#feature-matrix)
- [Architecture](#architecture)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [Enabling free live providers](#enabling-free-live-providers)
- [API reference](#api-reference)
- [Five-minute walkthrough](#five-minute-walkthrough)
- [Project layout](#project-layout)
- [Testing and evaluation](#testing-and-evaluation)
- [Documentation](#documentation)
- [Honest limitations](#honest-limitations-read-before-demoing)

---

## Feature matrix

Milestone 1 in full, plus the deterministic, credential-free parts of Milestones 2–4 and a
policy-bounded agent (Milestone 5). Live external providers are real adapters gated behind
explicit capability declarations — **never mocked as collected evidence**.

| Area | Status | Notes |
|---|---|---|
| Cases, RBAC (owner/analyst/reviewer/viewer), case isolation | ✅ | Membership checked on every read/write; unknown case → 404, never 403 |
| Authorized CSV/JSON imports, multipart image upload | ✅ | Raw snapshots preserved before normalization; MIME validated by signature, not extension |
| Evidence model + typed graph (15 relationship types, 4 derivation classes) | ✅ | PostgreSQL-ready schema; SQLite for zero-infra local dev |
| Jobs: lifecycle/outcome separation, SSE, cancel, idempotency, crash reconciliation | ✅ | In-process runner locally; Celery contract in `worker.py` |
| Image pipeline: SHA-256, DCT pHash, sliding-window region match, EXIF GPS | ✅ | 5 honest match categories incl. explicit `no_match` |
| Comments: dedup, coverage honesty, multilabel en/hi/Hinglish rules, spans | ✅ | Uncalibrated label declared on every result |
| Coordination: episode features, rarity, timing-precision rules, alternatives | ✅ | Review candidates only — no fabricated probabilities |
| Claims: proposition extraction, query-plan generation, imported fact-check matching | ✅ | Live Google Fact Check adapter optional; no-result ≠ false |
| Photo-to-location: metadata-reported vs insufficient, no invented places | ✅ | Vision/OCR path stays disabled until a provider is configured |
| Findings + reviewer workflow + full audit trail | ✅ | Reversible, append-only review states |
| Exports: PDF (Unicode/DejaVu), HTML, CSV, JSON + redaction + SHA-256 manifest | ✅ | Expiring signed-style links; CSV-injection guarded |
| Bounded agent `POST /agent/run`: plan → policy → allowlisted tool loop | ✅ | Step/time budgets, explicit stop reasons, prompt-injection treated as data |
| React + TypeScript + Cytoscape.js workspace (8 tabs) | ✅ | Shapes *and* labels, not color alone; mobile summary-first |
| Security: SSRF guard, signature validation, size/pixel caps, log-secret hygiene | ✅ | See [`docs/SECURITY.md`](docs/SECURITY.md) |
| **Live** YouTube comments import, Google Fact Check, Groq/Gemini/OpenRouter LLM | 🔑 key-gated | Shipped in `services/providers/` + Connectors tab; free keys; missing key → honest `not configured` |
| OCR, reverse image search, Instagram/Facebook, Reddit (approval-gated), Jev | ⛔ disabled/pending | Explicit statuses — import path remains available meanwhile |
| Exposure-check module | ⛔ out of MVP | Intentionally excluded per master-prompt section 20 |

---

## Architecture

```
┌──────────────────────────── Browser (React 19 + TS + Cytoscape.js) ───────────────────────────┐
│  StartScreen · Workspace (Graph · List · Comments · Findings · Compare · Agent · Connectors …) │
└───────────────────────────────┬───────────────────────────────────────────────────────────────┘
                                 │  versioned REST /api/v1  (dev proxy :5173, preview :4173)
┌───────────────────────────────▼──────────────────────── FastAPI ──────────────────────────────┐
│ routers: cases · runs · graph · comments · exports · agent · connectors                        │
│ services: jobs · pipeline · images · comments · coordination · claims · location · graph ·     │
│           exports · connectors · agent (bounded) · providers/ (llm · youtube · factcheck …)    │
│ security: RBAC · SSRF blocklist · signature checks · redaction · prompt-injection-as-data      │
└───────┬───────────────────┬──────────────────────┬───────────────────────┬────────────────────┘
        │ SQLAlchemy/Alembic│ local disk / S3-MinIO │ optional Celery+Redis  │ optional providers
        ▼                   ▼                        ▼                        ▼
   SQLite / PostgreSQL   object storage          worker.py contract      Groq · Gemini ·
                                                                          OpenRouter · YouTube ·
                                                                          Google Fact Check
```

**Evidence-first graph semantics.** Every edge carries a named meaning, origin, derivation
class (`fact | similarity | hypothesis | note`), method string and evidence IDs. Hypotheses
are rendered dotted-purple and can never be silently promoted to facts. Image matches follow
a fixed precedence: exact SHA-256 → dual pHash+pixel (`likely_same_visual_source`) →
region correlation (`partial_region_match`) → near-threshold pHash (`related_scene`) →
`no_match`, via method `phash-v1(dct64)+grayscale-correlation+sliding-window`.

---

## Quickstart

Requires Python 3.13+ and Node 20+. No Docker, database server or API key needed for the
full offline workflow.

### One-shot with Make

```bash
make install      # backend + frontend dependencies
make fixtures     # synthetic, clearly-labeled demo images (once)
make run-api      # FastAPI  → http://localhost:8000  (Swagger at /docs)
make run-web      # Vite dev → http://localhost:5173  (proxies /api → :8000)
# or the production web build:
make web          # vite preview → http://localhost:4173
make seed         # populate a demo case against the running API
make test         # 49 pytest tests
make eval         # fixture evaluation harness (5/5 labeled cases)
```

### Manual

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python fixtures/make_fixture_images.py
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

### Demo login (development only)

| Role | Token | Can do |
|---|---|---|
| Owner | `dev-token-owner` | Everything, incl. membership and exports |
| Analyst | `dev-token-analyst` | Imports, runs, agent, connectors |
| Reviewer | `dev-token-reviewer` | Findings review workflow |
| Viewer | `dev-token-viewer` | Read-only |

### Model Context Protocol (MCP) Server

Scamurai provides a native MCP server for AI coding assistants and autonomous agents (Antigravity, Claude Desktop, Cursor), enabling direct evidence extraction and disinformation analysis without external API keys:

```bash
python backend/scamurai_mcp.py
```

**Available MCP Tools:**
- `scamurai_analyze_media`: Extract SHA-256, DCT pHash, and EXIF GPS coordinates from suspect images.
- `scamurai_analyze_comments`: Multilingual (Hindi/English/Hinglish) comment NLP classification and span detection.
- `scamurai_detect_coordination`: Temporal clustering and lexical repetition analysis across multiple accounts.
- `scamurai_extract_claims`: Decompose post text into verifiable propositions and fact-check search queries.

### Docker (full stack)

```bash
cp .env.example .env
docker compose up --build
# Postgres + Redis + MinIO + API + Celery worker + frontend
```

The SQLite/in-process path exists so the smallest runnable milestone needs no
infrastructure; switch via `PS03_DATABASE_URL` and `PS03_REDIS_URL`.

---

## Configuration

All settings are env-driven, `PS03_`-prefixed, and read by `backend/app/config.py`
(pydantic-settings). Copy `.env.example` → `.env` (gitignored — **secrets never enter the
repo, logs, exports or browser bundles**).

| Variable | Purpose | Default |
|---|---|---|
| `PS03_DATABASE_URL` | SQLite locally; `postgresql+psycopg://…` in Docker | `sqlite:///./ps03_dev.db` |
| `PS03_STORAGE_DIR` / `PS03_S3_*` | Local disk or S3/MinIO object storage | `./var/storage` |
| `PS03_REDIS_URL` | Enables the Celery worker path when set | empty (in-process jobs) |
| `PS03_MAX_SEED_URLS`, `PS03_MAX_DEPTH`, `PS03_MAX_NEW_ENTITIES`, `PS03_RUN_DEADLINE_SECONDS` | Section-4 prototype guardrails (server-clamped) | 5 / 2 / 200 / 600 |
| `PS03_PHASH_DISTANCE_THRESHOLD`, `PS03_PIXEL_CORRELATION_THRESHOLD`, `PS03_NEAR_DUPLICATE_RATIO` | Image/coordination tuning | 5 / 0.82 / 0.88 |
| `PS03_JWT_SECRET`, `PS03_CORS_ORIGINS`, `PS03_EXPORT_LINK_TTL_SECONDS` | Security | change-me / localhost / 3600 |
| `PS03_LLM_PROVIDER` | `groq` · `openrouter` · `gemini` | empty (deterministic rules only) |
| `PS03_LLM_API_KEY`, `PS03_LLM_BASE_URL`, `PS03_LLM_MODEL_ID` | OpenAI-compatible LLM route | empty |
| `PS03_GEMINI_API_KEY` | Native Gemini route | empty |
| `PS03_YOUTUBE_API_KEY` | Live YouTube commentThreads import | empty |
| `PS03_GOOGLE_FACTCHECK_API_KEY` | Live Claim Search | empty |
| `PS03_REDDIT_CLIENT_ID/SECRET/USER_AGENT` | Approval-gated Reddit OAuth | empty |

---

## Enabling free live providers

Every adapter ships today and activates the moment a key is present in `.env`; the
`/capabilities` endpoint and Connectors tab flip from `not_configured` to `configured`
automatically. All free tiers, no credit card:

| Provider | Free quota (verified Oct 2026) | Gives you |
|---|---|---|
| **Groq** (recommended) | 30 req/min, 1,000 req/day per model, gpt-oss-20b/120b | Agent LLM steps (OpenAI-compatible) |
| Google Gemini AI Studio | ~250–1,500 req/day, Flash models | Same, native endpoint (free prompts may be used for training) |
| OpenRouter | 50 req/day on `:free` models, one key | Same, OpenAI-compatible |
| YouTube Data API v3 | 10,000 units/day; comment page = 1 unit | Public video comments + replies, key-only auth |
| Google Fact Check Tools | Free Claim Search | Published fact-checker ratings with source URLs |

👉 **Exact click-by-click signup steps, quotas and env snippets:
[`docs/REQUIRED_CREDENTIALS.md`](docs/REQUIRED_CREDENTIALS.md) (Hinglish).**
Instagram (Business/Creator only) and Reddit (2025 manual-approval gate) are documented there too.

Design guarantees: provider content always reaches the LLM as **untrusted data**;
`429`/transport failures become typed outcomes (`rate_limited`, `unavailable`), never
fabricated evidence; query-string API keys are kept out of logs.

---

## API reference

All routes are versioned under `/api/v1`, require a bearer token, and enforce per-case
membership. Interactive Swagger: **http://localhost:8000/docs**.

| Method & path | Purpose |
|---|---|
| `POST /cases` · `GET /cases` · `GET /cases/{id}` | Case lifecycle (server-clamped guardrails) |
| `GET /cases/{id}/capabilities` | Honest provider/config status matrix |
| `POST /cases/{id}/inputs` · `POST /cases/{id}/uploads` | URL/text inputs, signature-validated uploads |
| `POST /cases/{id}/runs` · `GET /cases/{id}/jobs/{jid}` · `POST …/cancel` | Idempotent workflow jobs + SSE at `/events` |
| `POST /cases/{id}/transforms` | Bounded single transforms |
| `GET /cases/{id}/graph` · `POST /graph/path` · `…/nodes/{nid}/pin` | Typed graph, provenance paths, layout pins |
| `GET /cases/{id}/compare` | 2–4 account comparison (separated fact/signal/unknown sections) |
| `GET /cases/{id}/comments` · `POST …/analyses` | Comments + transparent rule analyses |
| `GET /cases/{id}/findings` · `POST …/reviews` | Findings buckets and reviewer workflow |
| `GET /cases/{id}/evidence/{eid}` | Evidence chain with origin and derivation |
| `POST /cases/{id}/agent/run` | Bounded agent: `{goal, step_budget≤20, client_idempotency_key}` → 202 |
| `POST /cases/{id}/connectors/youtube/import` | Live bounded comment import (key-gated) |
| `POST /cases/{id}/connectors/factcheck/search` | Live fact-check search (key-gated) |
| `POST /cases/{id}/exports` · `GET …/exports/{eid}/download` | Redacted exports with SHA-256 manifest |
| `GET /cases/{id}/audit` | Append-only audit trail |

---

## Five-minute walkthrough

> 📖 Hinglish step-by-step: [`docs/USAGE.md`](docs/USAGE.md) — login, upload, workflows,
> graph reading, reviews, agent, connectors, exports, testing.

1. Sign in as **Owner**, create a case.
2. Upload `backend/fixtures/posts.json`, `comments.csv`, `factchecks.json` and the images
   in `backend/fixtures/images/` (or `make seed`).
3. Run workflows from the toolbar: **image pipeline → comments → coordination → claims →
   location**; watch stages live (SSE/polling).
4. Click any edge — the drawer shows derivation class, statement, evidence IDs, method and
   limitations. Hypothesis edges are dotted and can never be silently promoted.
5. **Findings**: review facts/signals/unknowns/conflicts; sign in as **Reviewer** to
   accept/reject/request-more-evidence.
6. **Compare** 2–4 accounts; **Agent** runs a policy-bounded plan; **Connectors** pulls
   live YouTube comments / fact-checks once keys are set.
7. Export a redacted PDF/HTML/CSV/JSON — each artifact carries a SHA-256 manifest.

---

## Project layout

```
ps03/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, startup, safe error handlers, log hygiene
│   │   ├── config.py            # env-driven PS03_ settings & guardrails
│   │   ├── models.py            # evidence-first relational schema
│   │   ├── registry.py          # 15 typed relationships + transform contracts
│   │   ├── security.py          # RBAC, SSRF, signatures, redaction
│   │   ├── routers/             # cases · runs · graph · comments · exports · agent · connectors
│   │   └── services/
│   │       ├── agent.py         # bounded agent, tool allowlist, policy & budgets (§16)
│   │       ├── providers/       # llm (groq/openrouter/gemini) · youtube · factcheck · reddit
│   │       ├── connectors.py    # capability declarations (honest not_configured states)
│   │       └── …jobs, pipeline, images, comments, coordination, claims, location, exports, graph
│   ├── alembic/                 # migrations (create_all used in SQLite dev)
│   ├── fixtures/                # synthetic, clearly labeled demo data (8 images + JSON/CSV)
│   ├── scripts/                 # seed_demo.py · evaluate.py
│   ├── tests/                   # 49 tests: acceptance gates, agent policy, providers (mocked HTTP), RBAC
│   └── worker.py                # optional Celery adapter
├── frontend/
│   └── src/
│       ├── components/          # 13 components incl. GraphCanvas, AgentView, ConnectorsView …
│       └── lib/                 # typed API client + types
├── docker-compose.yml           # db · redis · minio · api · worker · frontend
├── Makefile                     # install · fixtures · test · eval · run-api · run-web · web · seed · clean
├── .env.example                 # all settings documented; copy to gitignored .env
└── docs/                        # ARCHITECTURE · SECURITY · INTEGRATIONS · USAGE · REQUIRED_CREDENTIALS
```

---

## Testing and evaluation

```bash
make test                                  # 49 passing, hermetic: temp DB, mocked provider HTTP
cd backend && python scripts/evaluate.py   # 5/5 labeled fixture cases
```

The suite covers the section-21 acceptance gates, the agent's policy layer (unknown tools,
cross-case denial, disabled providers, step/time budgets, prompt-injection-as-data),
provider adapters (typed `not_configured` / `rate_limited` / `unavailable` outcomes,
pagination, 403 quota semantics), adversarial image/comment fixtures and RBAC isolation.
Provider tests never touch the network — all HTTP runs through `httpx.MockTransport`, and
the test harness clears credential env vars so a developer `.env` can never leak in.

---

## Documentation

| Doc | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Component design, data flow, graph semantics |
| [`docs/SECURITY.md`](docs/SECURITY.md) | RBAC, SSRF, secret handling, redaction, injection defenses |
| [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) | Real-vs-mocked matrix, outcome vocabulary, provider enablement |
| [`docs/USAGE.md`](docs/USAGE.md) | Hinglish end-to-end usage walkthrough |
| [`docs/REQUIRED_CREDENTIALS.md`](docs/REQUIRED_CREDENTIALS.md) | Hinglish free-tier key signup steps, quotas, env vars |

---

## Honest limitations (read before demoing)

- Without keys, connectors honestly report `not_configured` / `access_required`; the
  offline import path and all deterministic pipelines remain fully functional.
- The comment classifier is a transparent, **uncalibrated** rule layer; precision, recall
  and calibration must be measured on representative Hindi/Hinglish data before any
  production accuracy claim — the system never invents accuracy numbers.
- pHash thresholds are configurable engineering defaults validated on fixtures, not
  forensic certainties; every match category carries its method and limits.
- Dev tokens are a local convenience, not an identity system; replace with an IdP before
  deployment, and set a real `PS03_JWT_SECRET`.
- Legal admissibility (e.g. BSA Section 63), DPDP compliance and retention lawfulness
  require jurisdiction-specific review — hashes are integrity aids, not certifications.
