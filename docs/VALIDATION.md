# Verification record — 2026-10-24

This is a point-in-time implementation/connectivity record, not an accuracy certification, production-readiness guarantee or promise of third-party availability.

## Automated checks

| Check | Result |
|---|---|
| `cd backend && python -m pytest tests/ -q` | **67 passed**; six upstream/deprecation warnings |
| Fresh Alembic upgrade + `alembic check` | Passed; model and migration head agree |
| Disposable `0002 → 0001 → 0002` | Passed |
| Disposable `head → base → head` + `alembic check` | Passed |
| Existing preview DB backup, stamp `0001`, upgrade `0002`, model check | Passed; real case and provenance preserved |
| `cd frontend && npm run build` | TypeScript and Vite production build passed; 180 modules |
| `cd frontend && npm run test:e2e` | **10 passed** in Chromium, including production Pages route recovery |
| Axe WCAG 2/2.1 A/AA scan, 10 screens | **0 detectable violations** on the QA corpus; automated scope only |
| `bandit -q -r app worker.py -ll` | Clean |
| `pip-audit -r requirements.txt` | No known vulnerabilities |
| `npm audit --audit-level=moderate` | **0 vulnerabilities** |
| Existing fixture evaluation | Completed; expected image categories observed, 5/5 comment fixture labels present, negative-control states retained |
| Multilingual diagnostic | Executed; 14 synthetic pairs, limitations retained below |
| Experiment notebook validation | Valid nbformat JSON, 7 cells, all code compiles, no saved outputs |
| Real Compose/PostgreSQL/MinIO/Celery runtime | CI smoke implemented; **not run locally because Docker is unavailable** |

The Playwright checks:

1. Create an isolated, clearly labelled QA case through the real API; verify narrative, map, network, media and all 11 API/access rows render API-derived data without runtime errors.
2. Verify there is no demo control, normalize a pasted `Bearer …` token, accept a real API-backed finding and verify its review state refreshes.
3. Use a 390×844 viewport; verify no page-level horizontal overflow in the workspace and account detail views.
4. Open account and post evidence through global search; reload the resulting case/tab/entity deep links.
5. Save an audited alert decision and verify its status/note survive direct alert deep-link reload.
6. Configure a mocked remote HTTPS API before login; reject an invalid scheme, verify CORS/token behavior, and confirm a 401 clears authentication without losing the backend URL.
7. Abort the live cases request; verify a visible transport error and no investigation or synthetic/demo evidence substitution.
8. Scan login, case selection, Overview, Alerts, Accounts, Narratives, Network, Geospatial, Media, Findings and Connectors using axe WCAG A/AA rule tags. All detected rule impacts are gated, and the JSON report is retained as a CI artifact.
9. Emulate production Pages responses using the real `dist/`; recover nested case/alert, account and post path-style URLs with query/entity preservation and working assets.
10. Request an unknown Pages route; verify an honest branded 404 and safe workspace link without substituting investigation data.

Automated accessibility scans do not replace manual keyboard, screen-reader, zoom, reflow or cognitive-accessibility review. The tested 390px viewport had no page-level horizontal overflow.

## Static Pages diagnosis and route recovery

Before the new deployment, live no-cache checks found the portfolio root `/` at 200, `/scamurai` at 301, `/scamurai/` and its query-based deep links/assets at 200, but **`/scamurai/alerts` at 404 with the GitHub Pages not-found HTML**. This is a path-style deep-link hosting issue, not a missing backend or evidence fallback.

The build now includes `frontend/public/404.html`. Production-emulation tests pass for nested case/alert, account and post recovery, existing-query preservation, assets and unknown-route handling. CI also requires the `404.html` artifact. **Live fixed-route verification is pending the new push/Pages deployment and is not claimed here.**

## Migration and preview-data verification

A pre-migration copy of the actual development SQLite database was backed up, stamped at the matching baseline, upgraded to `0002`, and checked against model metadata. After the final browser runs, only clearly labelled Playwright QA cases were deleted with foreign-key enforcement; their case-storage directories were removed.

Retained real preview case:

```text
4d5fdab2-b8bc-4d84-8a5d-f8b133c5b06e
Live public-source validation — Mastodon
1 case / 3 posts / 2 accounts
3/3 posts have first_seen_at, collected_at and source timestamps
foreign_key_check: clean
alembic check: no new upgrade operations
```

Backups in the validation environment: `/tmp/scamurai-dev-pre-0002.db`, `/tmp/scamurai-dev-pre-final-qa-cleanup.db` and `/tmp/scamurai-dev-pre-pages-qa-cleanup.db`. These are local operational artifacts, not repository files.

## Multilingual and semantic diagnostic

The diagnostic runs the actual case-corpus TF-IDF/cosine implementation over `backend/fixtures/multilingual_narratives.json`. It is a tiny synthetic diagnostic, **not a representative benchmark**.

| Track | Result | Interpretation |
|---|---|---|
| Same-language lexical, 4 pairs | 4 true positives; Hindi pair cosine **0.896** | Unicode combining-mark regression fixed; no claim of general language accuracy |
| Cross-lingual semantic equivalence, 4 pairs | 4 lexical false negatives | Production has no semantic embedding model; lexical zero/low is not semantic dissimilarity |
| Different-narrative controls, 6 pairs | 5 true negatives, **1 false positive** | Different-place/shared-template text can cross 0.48; analyst review remains necessary |
| Overall, 14 pairs | TP 4 / FP 1 / TN 5 / FN 4; empty-token pairs 0 | Diagnostic bookkeeping only, not production precision/recall/calibration |

The Unicode fix preserves combining marks during normalization and tokenization; before the fix, Devanagari words were split/corrupted. Tests now lock this behavior.

No semantic embedding model was executed. `notebooks/multilingual_semantic_evaluation.ipynb` is an optional experiment with blank model ID/revision and no saved output. It does not transfer the lexical 0.48 threshold to embeddings and must not be used for production ingestion, sensitive storage, secrets, public APIs or always-on alerts.

## Live public-source spot checks

These earlier checks used the running FastAPI service and preserved their resulting evidence records. Connectivity is not an accuracy benchmark.

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
- This real Mastodon case is the only case retained in the cleaned preview.

### Media screening without a configured model

The `media_forensics` job completed and screened one uploaded QA image. The saved result reported:

```text
model_result.status = not_configured
model_result.synthetic_score = null
configured_model_results = 0
```

This verifies the required honest no-model state rather than a fabricated deepfake confidence.

## Operational boundaries still requiring deployment validation

- The real Compose smoke must pass in GitHub Actions before the new Pages deployment. Local Docker execution was not available.
- Production OIDC verification is implemented and tested with signed tokens, but no live external IdP soak test is claimed.
- The browser accepts bearer access tokens; interactive OIDC Authorization Code + PKCE/refresh-token/session flow is not implemented.
- Celery/S3 contracts have unit regressions and a concrete real-stack smoke; production broker/worker loss, S3 policy and load behavior still require environment-specific testing.
- Bot/deepfake/model precision, recall, calibration and operational thresholds are not established. Video deepfake support is not claimed.
- Platform-wide origin, reach, account ownership or orchestration attribution is not established.
- Continuous near-real-time ingestion is not implemented; analytics run on demand over collected case data.
- Production security, legal admissibility, jurisdiction-specific privacy compliance and manual accessibility review remain deployment responsibilities.
