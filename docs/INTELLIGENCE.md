# Intelligence methods, provenance and interpretation

This document describes what the analytics actually compute. It is a method reference, not an accuracy certification.

## Evidence language

| Layer | Examples | Permitted interpretation |
|---|---|---|
| Source observation | Imported post text, timestamp, URL, DNS answer, registry event, file hash | Observed from the identified source at the recorded collection time |
| Deterministic transform | Normalization, exact-text comparison, pHash, metadata extraction, aggregate count | Recomputable under the stated method and input coverage |
| Heuristic signal | TF-IDF narrative candidate, timing regularity, acceleration, geo spike | Review cue with alternatives; not intent or identity attribution |
| Optional model output | Configured image-classifier labels and scores | Model-specific, uncalibrated output requiring independent validation |
| Human decision | Accepted, rejected, needs more evidence | Reviewer decision attached to a finding, not an automatic truth label |

No heuristic or model result is silently promoted to a source fact. The investigation runtime is live-only; clearly labelled synthetic records are confined to automated QA/evaluation and are never used as a live-error fallback.

## Narrative candidates and propagation

Implementation: `backend/app/services/analytics.py`.

1. Text is NFKC-normalized and case-folded. Unicode letters/numbers and combining marks are preserved, so Indic vowel signs/virama are not deleted during punctuation normalization. Tokens of at least three characters are retained; numeric tokens and a small English/Hindi/Hinglish stopword list are removed.
2. Lexical TF-IDF vectors are computed within the case corpus.
3. Exact normalized text or cosine similarity `>= 0.48` joins posts into candidate clusters.
4. The latest 500 collected posts are the clustering input; `narrative_input_truncated` discloses truncation.
5. Hour/day/week buckets are selected from observed span. Undated counts remain visible.
6. Representative posts, top terms, account order, timestamps and evidence post IDs are returned.

**Earliest observed** is the earliest timestamp in that candidate cluster and collected corpus. It is not first uploader, original author, campaign originator, or platform-wide first occurrence.

Lexical similarity can group quotations, press releases, breaking-news updates, hashtags and ordinary viral sharing. Short texts, code-switching, sarcasm and translated retellings require human review. No multilingual embedding/semantic model is configured in production: a low cross-lingual lexical cosine is not semantic dissimilarity, and the method does not claim translation-level recall.

`backend/scripts/evaluate_multilingual.py` runs a small synthetic pairwise diagnostic against this exact method. `notebooks/multilingual_semantic_evaluation.ipynb` supports an optional, separately reviewed public embedding-model experiment. Neither is a representative accuracy benchmark or a production ingestion path.

## Narrative-acceleration review cue

A candidate needs at least four timeline buckets. The latest bucket is compared with the preceding three. A cue requires:

```text
latest >= 3
account_count >= 2
latest >= 2 * max(previous_three_bucket_mean, 0.25)
```

The attention value is a bounded rule score using acceleration, latest count and account count. The response includes baseline values, ratio, formula rule and evidence IDs. It is not a probability. A real-world event or changed import coverage can produce the same cue.

## Persistent review cues and evidence completeness

Narrative, geo, coordination and data-gap cues are reconciled into persistent case alert rows. Active/inactive history, evidence IDs, review state, priority, analyst note and review timestamps survive recomputation. Resolved/dismissed decisions are not silently reset by an analytics refresh; reviewer/owner changes create audit events.

For narrative and coordination cues, an evidence-completeness screening value is:

```text
100 * (
  .30 * min(visible_evidence_posts / 20, 1)
+ .30 * source_timestamp_coverage
+ .40 * min(platform_diversity_count / 2, 1)
)
```

Scores with zero/one visible platform are capped at 60. The value measures visible evidence completeness only. It is uncalibrated, is not a truth/threat probability, and platform diversity is not necessarily independent corroboration. Geo/data-gap cues return `not_applicable` rather than an invented confidence value.

## Account-behavior indicators

For accounts with at least three collected posts, the current screening value is:

```text
100 * (
  .30 * cross_account_identical_text_ratio
+ .20 * within_account_duplicate_ratio
+ .20 * sub_60_second_interval_ratio
+ .15 * timing_regularity
+ .15 * min(posts_per_hour / 24, 1)
)
```

`posts_per_hour` is omitted from the rate component when the observed span is under one hour. Evidence coverage separately considers sample size, timestamp coverage and observed span. A review-recommended status requires both score and coverage thresholds.

This is **not bot probability**. Newsrooms, schedulers, community campaigns and ordinary reposting can produce similar values. The UI exposes raw features, triggered indicators, formula, coverage and limitations.

## Observed account network

Only case-graph account-to-account edges named `PUBLICLY_CROSSLINKS` or `POSSIBLY_COORDINATED_WITH` enter this view. Fact and hypothesis degrees remain separate. Connected components are computed over those observed edges.

PageRank and betweenness are computed separately for the fact and hypothesis edge classes. Betweenness is exact up to 200 nodes and sampled with at most 100 deterministic-seed source nodes above that size; graph-metric computation is skipped above 2,000 nodes. Louvain communities use deterministic seed 42. Bridge candidates are articulation points whose removal would disconnect the corresponding observed graph. All values describe this bounded case graph only.

Cascade depth is reported as unavailable unless a real repost/reply DAG is available; lexical similarity and timestamp order are not substituted for cascade edges. A component, community, centrality value or articulation point does not prove common ownership, coordination, intent, reach or influence.

## Geospatial baselines

Location observations come from imported/source-supplied metadata and preserve their source and precision. Display points are averages rounded to two decimal places, with intensity based on aggregate count. This is not current device/person tracking.

Groups below `SCAMURAI_GEO_MIN_GROUP_SIZE` distinct observed subjects (default 3) are suppressed, with suppressed group/observation counts reported. One prolific account cannot cross the threshold; unlinked posts remain separate observed subjects. Exact supplied points are labelled as approximate areas in display rather than represented as anonymous aggregates. This reduces incidental exposure but is not a complete re-identification guarantee.

When at least four time buckets exist, a geo review spike requires:

```text
latest >= 3
latest > previous_three_mean + 2 * population_standard_deviation
latest >= 2 * max(previous_three_mean, 0.5)
```

Insufficient baseline is reported instead of an anomaly. Small samples, changing collection and incorrect/spoofed metadata can create misleading spikes.

## Media screening and optional models

Deterministic observations include:

- SHA-256 and perceptual hash from the existing media pipeline.
- Selected EXIF/metadata fields and AI-tool-name strings.
- Possible C2PA/JUMBF byte markers, explicitly labelled as **not signature validation**.
- Bounded grayscale Gaussian-residual statistics.
- For JPEG only, a quality-90 recompression comparison with no universal manipulation threshold.

If `SCAMURAI_DEEPFAKE_MODEL_ID` is configured and optional dependencies are installed, the configured Hugging Face image classifier returns its raw labels/scores. Recognized positive/negative labels are aggregated into an explicitly uncalibrated score. Model ID, revision and semantics are retained. Load/inference failure produces `unavailable`; no model configuration produces `not_configured`; neither creates a fallback score.

This path is for images, not a claim of video/deepfake coverage. A high score does not prove manipulation and a low score does not prove authenticity.

## Public-source OSINT provenance

Each module has independent `successful`, `successful_empty`, `partial`, or failure/limited outcomes. Reports are canonicalized, SHA-256 hashed, stored as evidence snapshots, and linked to `SourceAccess` rows.

Post/account provenance distinguishes the source publication timestamp, `first_seen_at` and `collected_at`. Normalized imports must not silently treat an ingest timestamp as the source publication time; missing source timestamps remain unknown. UI propagation language is earliest observed inside the collected corpus, not originator attribution.

| Module | Method and official reference | Interpretation boundary |
|---|---|---|
| DNS | [Google Public DNS JSON API](https://developers.google.com/speed/public-dns/docs/doh/json); response `Status` is inspected | Point-in-time resolver view; CDN and resolver variation expected |
| RDAP | [IANA RDAP bootstrap](https://data.iana.org/rdap/dns.json), [RFC 9224](https://datatracker.ietf.org/doc/html/rfc9224), [RFC 9083](https://www.rfc-editor.org/rfc/rfc9083.html) | Registry/allocation data, not website intent or a person's physical location |
| Web | One bounded public page with manually checked redirects | Self-reported metadata/headers, not content truth or complete site crawl |
| Certificates | [crt.sh](https://crt.sh/) historical CT search, deduplicated and capped | Historical names, not complete/current host availability |
| Archive | [Wayback Availability API](https://archive.org/help/wayback_api.php) | One closest snapshot; no snapshot does not prove content never existed |
| Mastodon | [Public API access](https://docs.joinmastodon.org/client/public/) and [status methods](https://docs.joinmastodon.org/methods/statuses/) | One public hashtag page when the instance permits it; no private/unlisted coverage |

Relevant defensive design reference: [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html). URL validation and redirect checks are present, but production egress controls and connection-level DNS pinning remain necessary against rebinding/TOCTOU threats.

Provenance interpretation references:

- [C2PA explainer](https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html): cryptographically bound provenance is not content truth; the current byte-marker check is not a C2PA validator.
- [NIST AI 100-4](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-4.pdf): synthetic-content detection can vary across generators and transformations; no single technique is sufficient.

## Required operational validation

Before using a threshold or model for consequential decisions:

1. Build a representative labelled set for the languages, platforms, media generators and compression pipelines in scope.
2. Measure false positives/negatives, calibration and subgroup performance; retain the evaluation set and model/threshold versions.
3. Include benign breaking news, newsrooms, schedulers, quotations, hashtag campaigns and other negative controls.
4. Record collection coverage and access failures with every evaluation.
5. Require qualified human review and corroboration for attribution or enforcement action.
