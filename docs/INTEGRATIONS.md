# Real, configured, limited and unavailable integrations

Scamurai must not present a mock as collected evidence. Connector capabilities are available at `GET /api/v1/cases/{id}/capabilities`; individual source outcomes are stored and surfaced with the investigation.

| Component | Current implementation | Evidence/access rule |
|---|---|---|
| Authorized CSV/JSON import | Real local normalization and immutable input/evidence snapshots | Labelled as authorized/user-supplied import; it is not represented as live platform collection |
| File/image upload | Signature, size/decode checks, SHA-256 and media pipeline | Original bytes and derivatives remain distinct |
| Generic public web fetch | Real bounded `httpx` fetch with URL/redirect/response controls | Login walls, quota and transport failures become explicit outcomes |
| Public-infrastructure OSINT | Real keyless DNS-over-HTTPS, IANA/RDAP, web metadata, crt.sh and Wayback adapters | Independent module outcomes; canonical hash-snapshotted report; no failed-source fallback values |
| Mastodon public hashtags | Real official instance API adapter | One bounded public page when permitted; no private/unlisted statuses, reblogs imported as originals, or login bypass |
| YouTube comments | Real official Data API adapter; requires `SCAMURAI_YOUTUBE_API_KEY` | Disabled comments, quota and transport outcomes remain distinct; coverage denominator is not invented |
| Google Fact Check | Real Claim Search adapter; requires `SCAMURAI_GOOGLE_FACTCHECK_API_KEY` | A published match is source evidence; no match is not proof of falsity |
| Instagram / Facebook | Not configured in this build | Official reviewed OAuth/permissions are required; authorized import remains available |
| Reddit | OAuth helper/status only; approval-gated | Credentials alone do not establish approved API access; no live success is claimed |
| OCR | Disabled unless an actual provider is configured | No fabricated transcript |
| Reverse image search | Disabled until a provider, credentials, terms and data handling are configured | Search snippets would be leads, not verified source content |
| Deterministic media screening | Real hashes, selected metadata, possible provenance-marker bytes and pixel/JPEG measurements | Screening observations only; C2PA byte markers are not cryptographic verification |
| Optional synthetic-image model | Real configured Hugging Face image-classification inference | Raw labels and uncalibrated aggregation only; unavailable/not-configured states return no score |
| LLM planning/summarization | Adapters for Groq/OpenRouter/Gemini; deterministic local rules by default | Provider content is untrusted data; failures are typed, never replaced with invented analysis |
| Celery/Redis, PostgreSQL, S3/MinIO | Compose/worker contracts plus local in-process/SQLite/disk development path | Local development behavior is not represented as durable production infrastructure |

`SCAMURAI_` is the canonical environment prefix. Existing `PS03_` shell variables and `.env` entries remain supported; canonical values take precedence.

## Outcome vocabulary

Common source outcomes include:

```text
successful · successful_empty · partial · not_supported · login_required
permission_denied · rate_limited · unavailable · not_configured
```

A failed or restricted source is not a successful empty result. `successful_empty` is reserved for a source that actually responded with no matching records. Analytics also turns relevant access failures into visible data-coverage review cues.

## Live-only runtime and QA fixture boundary

The product frontend has no demo mode or demo route. Live API, authentication, provider, and network failures throw visible errors and never activate synthetic content. Clearly labelled synthetic records exist only in automated tests/evaluation fixtures; they are not a fallback investigation path and are not included in a clean preview. The old `make seed` showcase workflow has been removed.

## Enabling a provider safely

1. Add credentials server-side only; never place them in frontend code, prompts, exports or logs.
2. Set the corresponding setting and verify the capability state with a non-secret health check.
3. Record provider, query, collection time, result type and coverage limitations.
4. Exercise success, empty, access-denied, quota, malformed-response and transport-failure paths.
5. Revalidate any threshold/model on representative local data before making an accuracy claim.

Credential setup notes: [`REQUIRED_CREDENTIALS.md`](REQUIRED_CREDENTIALS.md). Method and official-source references: [`INTELLIGENCE.md`](INTELLIGENCE.md).
