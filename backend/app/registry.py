"""Registries: typed graph relationships and bounded Transforms.

The relationship registry defines which entity types an edge may connect; the
transform registry drives the right-click/Transform UI and server-side policy
checks. Nothing here executes model calls — it only declares contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# entity types
ACCOUNT = "account"
POST = "post"
COMMENT = "comment"
MEDIA = "media"
CLAIM = "claim"
EVIDENCE = "evidence"
PLACE = "place"
LOCATION = "location_finding"
COORDINATION = "coordination_candidate"

# derivation classes
FACT = "fact"
SIMILARITY = "similarity"
HYPOTHESIS = "hypothesis"
NOTE = "note"


@dataclass(frozen=True)
class RelationshipSpec:
    name: str
    source_types: frozenset[str]
    target_types: frozenset[str]
    derivation_class: str
    description: str


RELATIONSHIPS: dict[str, RelationshipSpec] = {
    spec.name: spec
    for spec in [
        RelationshipSpec("PUBLISHED", frozenset({ACCOUNT}), frozenset({POST}), FACT,
                         "Platform/import record attributes this post to this account"),
        RelationshipSpec("COMMENTED_ON", frozenset({ACCOUNT}), frozenset({POST}), FACT,
                         "Comment author reference on this post (author reference, not identity)"),
        RelationshipSpec("REPLIES_TO", frozenset({COMMENT}), frozenset({COMMENT, POST}), FACT,
                         "Preserved reply hierarchy from the source record"),
        RelationshipSpec("CONTAINS_MEDIA", frozenset({POST, COMMENT}), frozenset({MEDIA}), FACT,
                         "Source record contains this media file"),
        RelationshipSpec("ASSERTS_CLAIM", frozenset({POST, COMMENT}), frozenset({CLAIM}), FACT,
                         "Text span in this record states the verifiable proposition"),
        RelationshipSpec("LINKS_TO", frozenset({POST, COMMENT, EVIDENCE}), frozenset({EVIDENCE}), FACT,
                         "Recorded outbound link with normalized destination"),
        RelationshipSpec("EXACT_FILE_MATCH", frozenset({MEDIA}), frozenset({MEDIA}), FACT,
                         "Identical SHA-256 and byte length (file identity, not caption truth)"),
        RelationshipSpec("VISUAL_SOURCE_MATCH", frozenset({MEDIA}), frozenset({MEDIA}), SIMILARITY,
                         "Perceptual hash + local verification: likely same visual source"),
        RelationshipSpec("SEMANTICALLY_SIMILAR", frozenset({POST, COMMENT, CLAIM}),
                         frozenset({POST, COMMENT, CLAIM}), SIMILARITY,
                         "Embedding/lexical closeness — not proof of copying or shared ownership"),
        RelationshipSpec("PUBLICLY_CROSSLINKS", frozenset({ACCOUNT}), frozenset({ACCOUNT}), FACT,
                         "Explicit public link between profiles (still source-attributed)"),
        RelationshipSpec("POSSIBLY_COORDINATED_WITH", frozenset({ACCOUNT, COORDINATION}),
                         frozenset({ACCOUNT, COORDINATION}), HYPOTHESIS,
                         "Repeated aligned behavior across episodes; intent not established"),
        RelationshipSpec("GPS_METADATA_REPORTS", frozenset({MEDIA}), frozenset({PLACE}), FACT,
                         "Coordinates read from file metadata — editable, not visual confirmation"),
        RelationshipSpec("POSSIBLY_DEPICTS", frozenset({MEDIA, LOCATION}), frozenset({PLACE}), HYPOTHESIS,
                         "Visual candidate place; narrowest supported precision only"),
        RelationshipSpec("DERIVED_FROM", frozenset({MEDIA}), frozenset({MEDIA}), FACT,
                         "Crop/redaction/annotation derivative lineage"),
        RelationshipSpec("PRESERVED_AS", frozenset({MEDIA}), frozenset({EVIDENCE}), FACT,
                         "Original bytes preserved as a stored evidence snapshot"),
        RelationshipSpec("ANALYST_NOTE", frozenset({ACCOUNT, POST, COMMENT, MEDIA, CLAIM, EVIDENCE, PLACE}),
                         frozenset({ACCOUNT, POST, COMMENT, MEDIA, CLAIM, EVIDENCE, PLACE}), NOTE,
                         "Human note — visibly distinct from source facts"),
    ]
}


@dataclass(frozen=True)
class TransformSpec:
    name: str
    applies_to: frozenset[str]
    summary: str
    needs_external: bool = False
    external_provider_key: str | None = None
    estimated_cost_note: str = "local"
    limits_note: str = "Bounded by case policy (depth, entity, fetch and time caps)"
    fields: tuple[str, ...] = field(default_factory=tuple)


TRANSFORMS: dict[str, TransformSpec] = {
    t.name: t
    for t in [
        TransformSpec("import_authorized_posts", frozenset({ACCOUNT}),
                      "Import posts from an authorized CSV/JSON export for this account"),
        TransformSpec("import_comments", frozenset({POST}),
                      "Import permitted comments/replies with pagination and coverage record"),
        TransformSpec("extract_ocr", frozenset({MEDIA}),
                      "Extract visible text; output kept separate from the original image",
                      True, "ocr_provider", "external when an OCR provider is configured"),
        TransformSpec("find_exact_duplicates", frozenset({MEDIA}),
                      "SHA-256 exact-file matching inside the authorized corpus"),
        TransformSpec("find_visual_variants", frozenset({MEDIA}),
                      "Versioned perceptual hash retrieval plus local-feature verification"),
        TransformSpec("estimate_capture_location", frozenset({MEDIA}),
                      "EXIF GPS plus background-clue candidates; no exact pin without corroboration"),
        TransformSpec("analyze_comment", frozenset({COMMENT}),
                      "Multilabel contextual analysis with evidence spans and abstention"),
        TransformSpec("compute_coordination_features", frozenset({ACCOUNT, POST}),
                      "Repeated co-sharing, timing and rarity features over the selected corpus"),
        TransformSpec("extract_claims", frozenset({POST, COMMENT}),
                      "Split text into verifiable propositions preserving source spans"),
        TransformSpec("plan_claim_searches", frozenset({CLAIM}),
                      "Build approved dork-style query plan; external search remains a separate step",
                      True, "factcheck_provider"),
        TransformSpec("reverse_image_search", frozenset({MEDIA}),
                      "Approved reverse-search adapter; disabled until provider terms/quota are verified",
                      True, "reverse_search_provider"),
    ]
}
