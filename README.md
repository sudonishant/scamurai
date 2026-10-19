# PS-03 — Social Media Coordinated Disinformation Detection System

A browser-based, **evidence-first** Maltego-style investigation workspace. An authorized
user submits post URLs, public account references, images, text claims, and authorized
comment exports; the system preserves evidence, finds related content, detects patterns
consistent with possible coordination, assesses claims, and explains every conclusion on
an interactive typed graph with exportable reports.

The product is deliberately **an investigation tool, not an accusation engine**. Every
output separates:

1. **What is established** (source-supported facts),
2. **What is a signal/hypothesis** (algorithmic similarity, review candidates),
3. **What remains unknown** (insufficient evidence, inaccessible sources).

Shared content is never proof of common account ownership, coordination is never
automatically malicious, and an inaccurate claim never establishes deliberate deception.

---

## What is implemented in this build

This repository implements the master prompt's **Milestone 1 in full plus the
deterministic, credential-free parts of Milestones 2–4**, with Milestone 5 (bounded
agent / Jev) and live platform providers stubbed honestly behind capability declarations.

| Area | Status | Notes |
|---|---|---|
| Cases, RBAC (owner/analyst/reviewer/viewer), case isolation | ✅ | Membership checked on every read/write |
| Authorized CSV/JSON imports, multipart image upload | ✅ | Raw snapshots preserved before normalization |
| Evidence model + typed graph (15 relationship types, 4 derivation classes) | ✅ | PostgreSQL in prod schema; SQLite for local dev |
| Jobs: lifecycle/outcome separation, SSE, cancel, idempotency, crash reconciliation | ✅ | In-process runner locally; Celery contract in `worker.py` |
| Image pipeline: SHA-256, DCT pHash, sliding-window region match, EXIF GPS | ✅ | 5 honest match categories incl. `no_match` |
| Comments: dedup, coverage honesty, multilabel en/hi/Hinglish rules, spans | ✅ | Uncalibrated label declared on every result |
| Coordination: episode features, rarity, timing precision rules, alternatives | ✅ | Review candidates only — no fabricated probabilities |
| Claims: proposition extraction, query-plan generation, imported fact-check matching | ✅ | External fact-check/search providers are optional |
| Photo-to-location: metadata-reported vs insufficient, no invented places | ✅ | Vision/OCR provider path disabled when unconfigured |
| Findings + reviewer workflow + full audit trail | ✅ | Reversible, append-only review states |
| Exports: PDF (Unicode/DejaVu), HTML, CSV, JSON + redaction + manifest hashes | ✅ | Expiring signed-style links; CSV-injection guarded |
| Bounded agent (`POST /agent/run`): plan→policy→allowlisted tool loop, step/time budgets, explicit stop reasons | ✅ | Deterministic planner; LLM can later propose actions but never bypass policy (section 16) |
| React + TypeScript + Cytoscape.js workspace | ✅ | Shapes *and* labels, not color alone; mobile summary-first |
| Security: SSRF guard, signature validation, prompt-injection-as-data, size/pixel caps | ✅ | See `docs/SECURITY.md` |
| Live platform connectors, OCR, reverse image search, LLM agent, Jev | ⛔ disabled | Explicit "not configured/access required" — never mocked as real |
| Exposure-check module | ⛔ out of MVP | Per section 20, intentionally excluded |

**30 pytest tests pass**, covering the section-21 minimum acceptance gates, the bounded
agent's policy layer (unknown tools, cross-case denial, disabled providers, budgets,
prompt-injection-as-data), adversarial image/comment fixtures and RBAC isolation.

---

## Quickstart (no Docker, no external credentials)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python fixtures/make_fixture_images.py     # synthetic images (once)
uvicorn app.main:app --reload --port 8000
# API docs:  http://localhost:8000/docs
# Tests:     pytest -q
# Eval:      python scripts/evaluate.py
# Demo data: python scripts/seed_demo.py   (against a running server)
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api -> :8000
```

### Demo login (development only)

| Role | Token |
|---|---|
| Owner | `dev-token-owner` |
| Analyst | `dev-token-analyst` |
| Reviewer | `dev-token-reviewer` |
| Viewer | `dev-token-viewer` |

### Docker (Postgres + Redis + MinIO + API + Celery worker + frontend)

```bash
cp .env.example .env
docker compose up --build
```

The SQLite/in-process path exists so the smallest runnable milestone needs no
infrastructure; switch via `PS03_DATABASE_URL` and `PS03_REDIS_URL`.

---

## Five-minute walkthrough

1. Sign in as **Owner**, create a case (guardrails are clamped server-side).
2. Upload `backend/fixtures/posts.json`, `comments.csv`, `factchecks.json` and the
   images in `backend/fixtures/images/`.
3. Run the workflows from the workspace toolbar: **image pipeline → comments →
   coordination → claims → location**. Watch job stages live (SSE/polling).
4. Click any edge: the right drawer shows its derivation class, statement, evidence
   IDs, method and limitations. Hypothesis edges are dotted and can never be silently
   promoted.
5. Open **Findings**: established facts, signals, unknowns and conflicts are grouped;
   sign in as **Reviewer** to accept/reject/request-more-evidence.
6. Open **Compare**, pick 2–4 accounts: each pair gets shared content, public
   cross-links, timing and contradictory/insufficient evidence in separate sections.
7. Export a redacted PDF/HTML/CSV/JSON — each artifact carries a SHA-256 manifest and
   an expiring link.

---

## Repository layout

```
ps03/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, startup, safe error handlers
│   │   ├── config.py          # env-driven settings & guardrails
│   │   ├── models.py          # evidence-first relational schema
│   │   ├── registry.py        # typed relationships + transform contracts
│   │   ├── security.py        # RBAC, SSRF, signatures, redaction helpers
│   │   ├── routers/           # /api/v1 endpoints (section 17 contracts)
│   │   └── services/          # jobs, pipeline, images, comments, coordination,
│   │                          # claims, location, exports, connectors, graph
│   ├── alembic/               # migrations (autogenerate initial; create_all in dev)
│   ├── fixtures/              # synthetic, clearly labeled demo data
│   ├── scripts/               # seed_demo.py, evaluate.py
│   ├── tests/                 # 19 tests incl. acceptance gates & adversarial cases
│   └── worker.py              # optional Celery adapter
├── frontend/
│   └── src/
│       ├── components/        # graph, panels, comments, findings, compare, exports
│       └── lib/               # typed API client
├── docker-compose.yml
└── docs/                      # ARCHITECTURE, SECURITY, INTEGRATIONS
```

## Honest limitations (read before demoing)

- No live social-platform access is included; connectors honestly report
  `not_configured` / `access_required` / `import_available`.
- The comment classifier is a transparent, **uncalibrated** rule layer; precision,
  recall and calibration must be measured on representative Hindi/Hinglish data before
  any production claim.
- pHash thresholds are configurable engineering defaults validated only on fixtures.
- Dev tokens are not a real identity system; replace with an IdP before deployment.
- Legal admissibility (e.g. BSA Section 63), DPDP compliance and retention lawfulness
  require jurisdiction-specific review — hashes are integrity aids, not certifications.
