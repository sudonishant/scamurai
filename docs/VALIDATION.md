# Verification record — 2026-10-24

This is a point-in-time implementation/connectivity record, not an accuracy benchmark or a guarantee of third-party availability.

## Automated checks

| Check | Result |
|---|---|
| `cd backend && python -m pytest tests/ -q` | **58 passed**; six upstream/deprecation warnings |
| `cd frontend && npm ci && npm run build` | TypeScript and Vite 8 production build passed |
| `cd frontend && npm run test:e2e` | **5 passed** in Chromium |
| `cd frontend && npm audit --audit-level=moderate` | **0 known vulnerabilities** |

The browser tests:

1. Create their own case and six-post synthetic validation import through the live API; verify narrative, map, network, media and all 11 API/access rows render API-derived data without runtime errors.
2. Verify there is no demo control, paste a full `Bearer …` token to test normalization, accept a real API-backed finding, and verify its review state refreshes.
3. Use a 390×844 viewport; verify no page-level horizontal overflow and open the geospatial view.
4. Configure a mocked remote HTTPS API before login; reject an invalid URL scheme, verify CORS/token behavior, and confirm a 401 clears authentication without losing the backend connection.
5. Abort the live cases request; verify a visible transport error and that neither an investigation nor synthetic/demo evidence is substituted.

The browser suite needs FastAPI on `:8000` and Vite on `:5173`; it does not need an external provider or pre-seeded case. It creates development data in the configured development database.

## Live public-source spot checks

These checks used the running FastAPI service and preserved their resulting evidence records.

### `example.com` / `https://example.com/`

- DNS, authoritative RDAP and Wayback report: **3/3 modules successful**.
- Bounded web metadata and Certificate Transparency report: **2/2 modules successful**.
- Web parser observed title **Example Domain** and final URL `https://example.com/`.
- CT parser returned **6 deduplicated observed hostnames**, not truncated.

This establishes that the adapters made and parsed real public responses in this environment. It does not make registry, DNS, CT or archive data proof of campaign intent.

### Mastodon official public API

- Instance: `mastodon.social`
- Endpoint behavior: bounded public hashtag import, hashtag `factcheck`, limit 3
- Result: **3 statuses returned, 3 posts imported, 2 observed accounts**, 0 skipped reblogs
- Coverage note retained: one public hashtag page, no private/unlisted coverage and no platform-wide completeness claim.
- Clean preview state: the synthetic showcase and Playwright validation cases were removed after QA. This real Mastodon case is the only case retained in the preview; its three posts, two accounts and source-access records remain intact.

### Analytics from a clearly labelled synthetic import

A six-post/three-account validation bundle marked `SYNTHETIC_VALIDATION_IMPORT` produced:

- Six posts analysed for narratives; three observed accounts.
- One lexical narrative candidate spanning all six posts.
- A Darbhanga aggregate from supplied city-level test coordinates.
- Explainable geospatial-spike and narrative-acceleration review cues.

These values test the calculations and rendering path. They are not represented as live public events or detector accuracy.

### Media screening without a configured model

The `media_forensics` job completed and screened one uploaded image. The saved result reported:

```text
model_result.status = not_configured
model_result.synthetic_score = null
configured_model_results = 0
```

This verifies the required honest no-model state rather than a fabricated deepfake confidence.

## Not established by these checks

- Bot/deepfake/model precision, recall, calibration or operational thresholds.
- Video deepfake support.
- Platform-wide origin, reach, account ownership or orchestration attribution.
- Continuous near-real-time ingestion; analytics are on demand over collected case data.
- Production security, durable-worker behavior under load, legal admissibility, or jurisdiction-specific privacy compliance.
