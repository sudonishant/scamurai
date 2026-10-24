# Real vs mocked integrations

The system never presents a mock as collected evidence. Every connector declares
capabilities and an honest status, surfaced at `GET /api/v1/cases/{id}/capabilities`.

| Component | In this build | Production path | Evidence honesty rule |
|---|---|---|---|
| Manual CSV/JSON import | **Real, local** | Same | Labeled `authorized_import`; snapshot preserved |
| File/image upload | **Real, local** (signature, SHA-256, pHash, EXIF) | S3-compatible bucket | Separate original/derivative assets |
| Generic public web fetch | **Real**, SSRF-guarded httpx | Same with egress proxy | Login walls/429/5xx become explicit outcomes |
| Instagram / Facebook | **Not configured** | OAuth + official APIs after review | Shows `access_required`; import remains available |
| YouTube comments | **Live adapter shipped** (`POST /connectors/youtube/import`); active with free `SCAMURAI_YOUTUBE_API_KEY` | Official Data API v3, key-only | commentsDisabled/quota/transport failures become explicit `SourceAccess` outcomes; denominator never faked |
| Reddit | Status + OAuth helper shipped; approval-gated since 2025 | Manual Responsible Builder approval | Shows `not_configured` / `configured_pending_approval`; import remains available |
| OCR (e.g. Tesseract/Cloud Vision) | **Disabled** (`SCAMURAI_OCR_PROVIDER` empty) | Provider + license + quota check | Transform returns `insufficient_evidence` limitation, never fake text |
| Reverse image search (TinEye / Cloud Vision Web Detection) | **Disabled** | Adapter with verified terms/credentials | Snippets stay "leads" until the source is opened |
| Fact-check search | **Live adapter shipped** (`POST /connectors/factcheck/search`); active with free `SCAMURAI_GOOGLE_FACTCHECK_API_KEY`; imported library still works offline | Google Fact Check Tools API | No-result is never proof of falsity; response says so explicitly |
| LLM planning/summarization | **Adapter shipped** for Groq / OpenRouter / Gemini (`services/providers/llm.py`); activates only with a key; deterministic rules remain the offline default | OpenAI-compatible or Gemini endpoint, configured model ID | All content passed as untrusted data; JSON-only; 429/transport errors are typed, never fabricated output |

> 🔑 **Free-tier credentials, step-by-step (Hinglish): [REQUIRED_CREDENTIALS.md](REQUIRED_CREDENTIALS.md)** —
> exact signup steps, quota limits, env vars, and the minimum key set needed.
| Jev (Choice/Score/Noul) | **Not implemented** (section 16: optional/experimental) | Pilot against baseline classifier first | Confidence ≠ accuracy; abstention preserved |
| Celery + Redis | Compose config + `worker.py` contract | Durable broker with acks/late ack | Job state always in DB; idempotent tasks |
| PostgreSQL | Alembic + SQLAlchemy ready; SQLite default locally | Primary authoritative store | Same SQL dialect-targeted models |
| S3/MinIO | Compose config; disk storage locally | Private bucket, short-lived links | Metadata in DB, bytes in object store |
| Exposure-check module | **Absent by design** (section 20) | Only with verified lawful provider/consent | No leaked passwords/tokens/dossiers, ever |

## Connector outcome vocabulary

`successful · successful_empty · not_supported · login_required · permission_denied ·
rate_limited · unavailable · not_configured` — each is stored on `SourceAccess` and
shown in the UI. None of them means "nothing exists".

## Enabling a provider safely

1. Add credentials server-side only (env/secret manager); never in prompts, exports or
   frontend bundles.
2. Set the corresponding `SCAMURAI_*` setting; capabilities flip to `configured`.
3. Record provider, query image/text, retrieval time and result type per match.
4. Add contract tests using the provider's sandbox; keep the disabled-state tests.
5. Re-validate thresholds and retrain/recalibrate classifiers on representative
   Hindi/Hinglish data before any accuracy claim.
