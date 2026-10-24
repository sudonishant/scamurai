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

1. Unicode tokens of at least three characters are case-folded; numeric tokens and a small English/Hindi/Hinglish stopword list are removed.
2. Lexical TF-IDF vectors are computed within the case corpus.
3. Exact normalized text or cosine similarity `>= 0.48` joins posts into candidate clusters.
4. The latest 500 collected posts are the clustering input; `narrative_input_truncated` discloses truncation.
5. Hour/day/week buckets are selected from observed span. Undated counts remain visible.
6. Representative posts, top terms, account order, timestamps and evidence post IDs are returned.

**Earliest observed** is the earliest timestamp in that candidate cluster and collected corpus. It is not first uploader, original author, campaign originator, or platform-wide first occurrence.

Lexical similarity can group quotations, press releases, breaking-news updates, hashtags and ordinary viral sharing. Short texts, code-switching, sarcasm and translated retellings require human review.

## Narrative-acceleration review cue

A candidate needs at least four timeline buckets. The latest bucket is compared with the preceding three. A cue requires:

```text
latest >= 3
account_count >= 2
latest >= 2 * max(previous_three_bucket_mean, 0.25)
```

The attention value is a bounded rule score using acceleration, latest count and account count. The response includes baseline values, ratio, formula rule and evidence IDs. It is not a probability. A real-world event or changed import coverage can produce the same cue.

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

A component does not prove common ownership, coordination, intent, reach or influence. Graph degree is degree inside the collected case graph, not platform-wide audience influence.

## Geospatial baselines

Location observations come from imported/source-supplied metadata and preserve their source and precision. Display points are averages rounded to two decimal places, with intensity based on aggregate count. This is not current device/person tracking.

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
