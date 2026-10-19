# Security, privacy and operational reliability

Threat model and controls mapped to master-prompt section 19. Automated tests in
`backend/tests/test_security.py` exercise each control; passing tests are not a claim
of perfect security.

## Authentication & authorization

- Development bearer tokens are demo-only (`dev-token-*`). Deployment must replace the
  `get_current_user` dependency with an external identity provider/OAuth.
- **RBAC**: role rank `owner > analyst > reviewer > viewer`; writes require
  analyst+, reviews require reviewer+, exports require analyst+.
- **Case isolation is enforced per request**, not just at login: `require_case()`
  loads the membership on every read/write (graph, evidence, jobs, events, exports) and
  returns **404** (not 403) for concealed resources. Cross-case access is covered by a
  test asserting zero leakage.
- Client-supplied user IDs are never trusted as authority.

## SSRF defense (`security.assert_public_url`, connectors)

- Only `http`/`https` schemes; DNS resolution checked before every fetch.
- Loopback, RFC1918, link-local (incl. `169.254.169.254`), unique-local IPv6 and cloud
  metadata hostnames are blocked.
- Redirects are re-validated per hop via an httpx request hook; response size, timeout
  and content-type are bounded.
- Platform hosts without a configured connector return `not_configured`/`access_required`
  preflight records instead of being fetched.

## Untrusted content & prompt injection

- Posts, comments, OCR text, fetched pages and search results are treated as **data**,
  never instructions. The policy layer lives outside any model call; no credentials are
  placed in model context.
- The comment classifier recognizes instruction-like content
  (`ignore previous instructions`, `send the secret/API key`, `act as`, …) and labels it
  `prompt_instruction_in_content`; the text is stored verbatim and never executed
  (test included).
- HTML reports escape all dynamic content; CSV exports neutralize formula injection by
  prefixing cells starting with `= + - @ tab CR` (test asserts `'=1+1`).
- Error responses return code, safe message, retryability and a correlation ID — never
  stack traces or secrets.

## Upload safety

- Magic-byte signature validation, extension is not trusted (`validate_image_signature`).
- Bounded request size (`413`), Pillow pixel-count cap, bounded memory during decode.
- Executable content is never served or executed; object keys are server-generated.

## Data protection

- Private object storage (local disk or S3-compatible); metadata and object references
  live in the database, never the bytes.
- Redacted export mode masks author identifiers, emails and phone numbers; full
  evidence mode is a separate restricted action with a previewed difference.
- Download links expire (`PS03_EXPORT_LINK_TTL_SECONDS`; expired links return `410`).
- Audit log records case creation, imports, analyses, reviews and exports with actor IDs.
- Retention is per-case (`retention_days`); deletion must propagate to objects, indexes
  and provider obligations (deletion workflow is a deployment task).

## Reliability

- Idempotency keys on inputs, jobs and edges; duplicate-safe workers; replaying a run
  returns the same job with no duplicate nodes/comments/exports (test included).
- `reconcile_orphans()` marks interrupted jobs `failed/partial` on startup; collected
  evidence is preserved and reruns are safe.
- Bounded exponential backoff is the connector policy; permanent denials are never
  retried in a loop; rate limits (429) are honored and surfaced as job outcomes.
- Coverage honesty: non-comparable denominators never become percentages; unknown
  completeness never renders as 100%; login walls produce explicit access statuses, not
  "empty" results.

## Deployment checklist

- [ ] Replace dev tokens with an IdP; rotate `PS03_JWT_SECRET`.
- [ ] Run on PostgreSQL with Alembic migrations; back up and test restoration.
- [ ] Enable TLS, private buckets, least-privilege service accounts.
- [ ] DPDP Act / 2025 Rules and jurisdiction-specific privacy review before deployment.
- [ ] Legal review of evidence handling; do not label PDFs as certified evidence.
- [ ] Provider contracts (quota, retention, data handling) verified before enabling any
      OCR, reverse-search, fact-check, LLM or Jev integration.
