# Architecture

## Layered view

```
React 18 + TypeScript + Cytoscape.js (graph renderer behind a component interface)
        │  relative /api/v1 calls only; SSE for job progress (polling fallback)
        ▼
FastAPI (Pydantic validation, RBAC/case-membership gateway, SSRF-safe fetch layer)
        │                                   │
   sync request/response            bounded jobs (ThreadPool locally; Celery+Redis in prod)
        │                                   │
PostgreSQL (entities, typed edges, jobs,        services:
evidence, findings, audit)  ─────────────►      images · comments · coordination
SQLite in local dev                              claims · location · exports
        │
S3-compatible private object storage (local disk in dev): originals, snapshots, reports
```

A graph canvas does **not** require a graph database: nodes and typed edges live in
relational tables. Neo4j is only considered after measured traversal needs justify it.

## Evidence-first data principles

- Internal UUIDs, UTC timestamps, schema versions and case ownership on every record.
- Raw source representations are stored separately from normalized/corrected fields;
  OCR text, translations and normalized text never overwrite originals.
- Every `GraphEdge` carries a **derivation class**:
  `fact` (source-supported), `similarity` (algorithmic), `hypothesis` (review needed),
  `note` (analyst). The registry in `app/registry.py` constrains which entity types each
  relationship may connect.
- Analysis runs are versioned (`tool`, `model_version`, parameters, inputs, errors);
  derived results are superseded, never mutated in place. Merge/split are reversible
  audit operations, never deletions.

## Request lifecycle (section 5)

```
Input → auth + case policy → validation → original evidence preservation
     → normalized records → bounded analysis job → validated findings
     → graph/timeline updates → reviewer decision → export
```

`POST /runs` returns **HTTP 202** with `run_id`/`job_id`; heavy work never blocks a
request. Job **lifecycle** (`queued|running|waiting_for_access|waiting_for_review|
completed|failed|cancelled`) is stored separately from **outcome**
(`complete|partial|insufficient_evidence`). Cancellation is cooperative at checkpoints
and preserves collected evidence.

## Image pipeline (staged, section 9)

1. **File integrity** — SHA-256 + byte length; equal size alone is never a match.
2. **Candidate retrieval** — 64-bit DCT pHash (pure NumPy) with configurable Hamming
   threshold; bit agreement is labeled as representation agreement, not probability.
3. **Visual verification** — grayscale correlation plus a sliding-window region search
   for crops/screenshots, yielding `exact_file | likely_same_visual_source |
   partial_region_match | related_scene | no_match | uncertain`.
4. **Semantic embeddings** — only when a configured, permission-filtered index exists.
5. **External reverse search** — adapter disabled until provider terms/quota are verified.

## Coordination detection (section 13)

- Inverted indexes over exact text, near-duplicates, normalized URLs and visual groups —
  never all-pairs comparison.
- Events are **strong** only when distinctive *and* rare (or visual/near-duplicate);
  generic breaking-news lines, hashtags and one-upstream-article reposts stay weak.
- A pair becomes a review candidate only with repeated strong episodes, or one rare
  strong episode plus tight minute-precision timing. Day-level timestamps cannot produce
  minute-level synchronization claims; unknown timestamps count as missing, not zero.
- Output always carries corpus-only baseline labeling, alternative explanations, event
  lineage (copies of one upstream source are not independent corroboration), and review
  states — never a "probability of disinformation".

## Scoring discipline

No universal fake score exists. Separate panels hold evidence quality
(`Q = 30D + 25I + 20C + 15T + 10R`, checklist-driven, with explicit
`assessment_incomplete`), image match types, claim outcomes, comment categories,
coverage and review priority. Similarity distances, rubric scores, classifier
probabilities and human review states use distinct labels.

## Bounded agent posture (section 16)

Deterministic software owns hashing, parsing, authorization, pagination, dedup.
Model-facing steps (claim extraction, query planning, clue interpretation, summaries)
are isolated behind provider configuration; when no provider is configured the workflow
still completes honestly with query plans and `insufficient_available_evidence`.
Allowlisted typed tools, step/time/provider budgets and policy checks live outside the
model; arbitrary shell, SQL, cross-case retrieval and write actions are impossible by
construction.
