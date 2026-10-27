# Security, privacy and operational reliability

Threat model and controls mapped to master-prompt section 19. Automated tests in
`backend/tests/test_security.py` exercise each control; passing tests are not a claim
of perfect security.

## Authentication & authorization

- Development bearer tokens (`dev-token-*`) are local-only. `SCAMURAI_ENVIRONMENT=production`
  rejects development credentials, disables the development user directory and does not auto-seed users.
- Production OIDC bearer verification uses PyJWT's issuer JWKS client and validates signature,
  issuer, audience, expiry and `iss/aud/sub/exp/iat`. Only explicitly allowed algorithms are accepted
  (RS256 by default). OIDC is required in production unless a deliberately configured environment
  replaces it; incomplete production OIDC settings fail startup.
- Identities are mapped by issuer + subject to a pre-provisioned local user. Valid tokens do not
  self-register or self-assign roles. Use `backend/scripts/provision_oidc_user.py` for explicit
  onboarding and case membership.
- The browser currently stores and submits a bearer access token; interactive Authorization Code +
  PKCE, refresh-token handling and backend-for-frontend cookie sessions are not implemented. Add a
  trusted flow/gateway before public rollout and never place provider client secrets in `VITE_*`.
- **RBAC**: role rank `owner > analyst > reviewer > viewer`; writes require
  analyst+, findings/alert reviews require reviewer+, exports require analyst+.
- **Case isolation is enforced per request**, not just at login: `require_case()`
  loads the membership on every read/write (graph, evidence, jobs, events, exports) and
  returns **404** (not 403) for concealed resources. Cross-case access is covered by a
  test asserting zero leakage.
- Client-supplied user IDs are never trusted as authority. Production `/users` exposes only the
  current non-secret identity, not a directory of all users or development token hints.

## SSRF defense (`security.assert_public_url`, connectors)

- Only `http`/`https` schemes; credentialed URLs are rejected and DNS results are checked before each hop.
- Every non-global destination is rejected, including loopback, RFC1918, CGNAT, link-local,
  unique-local IPv6, mapped IPv4, reserved ranges and cloud metadata destinations.
- Redirects are followed manually (bounded count) and every target is revalidated; response
  size, timeout and content type are bounded.
- Platform hosts without a configured connector return `not_configured`/`access_required`
  preflight records instead of being fetched.
- **Residual risk:** validation-time DNS checks do not pin the address used by the subsequent
  socket connection and therefore do not alone eliminate DNS-rebinding/TOCTOU attacks. Use
  network-layer egress restrictions and connection-level DNS pinning where feasible for any
  internet-facing or multi-tenant deployment.

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
- Browser media previews retrieve protected bytes with the bearer token and use revocable
  local object URLs rather than unauthenticated `<img>` endpoint URLs.

## Data protection

- Private object storage is real: atomic same-filesystem local rename for development, or
  Boto3 `put_object`/`get_object` against S3/MinIO with an optional custom endpoint and IAM/default
  credential chain. Metadata and object references live in the database, never the bytes.
  Bucket policy, encryption, retention and network access remain deployment controls.
- Redacted export mode masks author identifiers, emails and phone numbers; full
  evidence mode is a separate restricted action with a previewed difference.
- Download links expire (`SCAMURAI_EXPORT_LINK_TTL_SECONDS`; expired links return `410`).
- Geospatial aggregation suppresses cells with fewer than the configured distinct-subject threshold
  (default 3). Exact supplied points are explicitly labelled rather than disguised as aggregates;
  this reduces incidental exposure but is not a complete re-identification guarantee.
- Audit log records case creation, imports, analyses, findings/alert reviews and exports with actor IDs.
- Retention is per-case (`retention_days`); deletion must propagate to objects, indexes
  and provider obligations (deletion workflow is a deployment task).

## Reliability

- Idempotency keys on inputs, jobs and edges; duplicate-safe workers; replaying a run
  returns the same job with no duplicate nodes/comments/exports (test included). With Redis
  configured, persisted jobs are dispatched by registered Celery task name to a real worker;
  local development may explicitly use the in-process executor. Missing Redis is not silently
  treated as a queued remote job.
- Celery uses late acknowledgement for crash recovery. That is at-least-once execution, not
  exactly-once delivery: handlers must remain idempotent and worker-loss/requeue behavior needs
  deployment-specific soak testing.
- `reconcile_orphans()` marks interrupted jobs `failed/partial` on startup; collected
  evidence is preserved and reruns are safe.
- Bounded exponential backoff is the connector policy; permanent denials are never
  retried in a loop; rate limits (429) are honored and surfaced as job outcomes.
- Coverage honesty: non-comparable denominators never become percentages; unknown
  completeness never renders as 100%; login walls produce explicit access statuses, not
  "empty" results.

## Deployment checklist

- [ ] Set production environment, disable dev auth, configure OIDC issuer/audience/JWKS and
      provision explicit identities; rotate `SCAMURAI_JWT_SECRET` for any legacy signed tokens.
- [ ] Provide a trusted browser OIDC/PKCE or session-gateway flow; do not distribute long-lived
      access tokens through chat, screenshots, URLs or frontend build variables.
- [ ] Run PostgreSQL with reviewed Alembic migrations; back up and test restoration and downgrade.
- [ ] Run Celery with the same DB/object-store configuration and verify durable worker recovery.
- [ ] Enable TLS, private buckets, least-privilege service accounts, rate limiting and centralized
      audit/log retention at the deployment gateway/platform.
- [ ] Enforce outbound egress policy; add connection-level DNS pinning where feasible and
      test redirect/rebinding defenses against the actual deployment network.
- [ ] DPDP Act / 2025 Rules and jurisdiction-specific privacy review before deployment.
- [ ] Legal review of evidence handling; do not label PDFs as certified evidence.
- [ ] Provider contracts (quota, retention, data handling) verified before enabling any
      OCR, reverse-search, fact-check, LLM or Jev integration.
