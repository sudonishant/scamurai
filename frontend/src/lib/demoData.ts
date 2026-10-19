import type {
  Case, CommentRow, Finding, GraphData, Job, Capability,
} from "./types";

export const DEMO_USERS = [
  { id: "u-owner", email: "alice.owner@investigation.internal", name: "Alice Owner (Lead)", token_hint: "dev-token-owner" },
  { id: "u-analyst", email: "bob.analyst@investigation.internal", name: "Bob Analyst (Investigator)", token_hint: "dev-token-analyst" },
  { id: "u-reviewer", email: "carol.reviewer@investigation.internal", name: "Carol Reviewer (Auditor)", token_hint: "dev-token-reviewer" },
  { id: "u-viewer", email: "dave.viewer@investigation.internal", name: "Dave Viewer (Observer)", token_hint: "dev-token-viewer" },
];

export const DEMO_CASE: Case = {
  id: "case-rain-photo-001",
  title: "Demo: Rain-Photo Coordination Investigation",
  purpose: "Synthetic authorized corpus demonstrating the full evidence-first investigation pipeline (Scamurai)",
  allowed_sources: ["https://twitter.com", "https://youtube.com", "authorized_exports"],
  date_from: "2026-10-15T00:00:00Z",
  date_to: "2026-10-19T23:59:59Z",
  languages: ["en", "hi"],
  retention_days: 90,
  limits: { max_seed_urls: 5, max_depth: 2, max_entities: 200, max_fetches: 20 },
  my_role: "owner",
  created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
};

export const DEMO_GRAPH: GraphData = {
  total_nodes: 11,
  total_edges: 12,
  truncated: false,
  nodes: [
    {
      id: "acc_1", entity_type: "Account", entity_id: "acc_1", label: "@breaking_quick_in", pinned: false,
      properties: { followers: 42100, verified: false, created: "2024-03-01", suspicion_score: "High" }
    },
    {
      id: "acc_2", entity_type: "Account", entity_id: "acc_2", label: "@daily_wire_news", pinned: false,
      properties: { followers: 18900, verified: false, created: "2024-03-01", suspicion_score: "High" }
    },
    {
      id: "acc_3", entity_type: "Account", entity_id: "acc_3", label: "@citizen_alert_x", pinned: false,
      properties: { followers: 2300, verified: false, created: "2025-01-11", suspicion_score: "Medium" }
    },
    {
      id: "post_1", entity_type: "Post", entity_id: "post_1", label: "Post #10842 (Breaking Floods)", pinned: false,
      properties: { timestamp: "2026-10-19T10:14:02Z", retweets: 1420, text: "URGENT: Entire district submerged in unexpected floods! Authorities missing." }
    },
    {
      id: "post_2", entity_type: "Post", entity_id: "post_2", label: "Post #10843 (Identical Text)", pinned: false,
      properties: { timestamp: "2026-10-19T10:14:05Z", retweets: 890, text: "URGENT: Entire district submerged in unexpected floods! Authorities missing." }
    },
    {
      id: "post_3", entity_type: "Post", entity_id: "post_3", label: "Post #10848 (Amplification)", pinned: false,
      properties: { timestamp: "2026-10-19T10:15:30Z", retweets: 310, text: "Check this out! Same photos being shared everywhere, stay safe!" }
    },
    {
      id: "img_1", entity_type: "Media", entity_id: "img_1", label: "rain_scene_a.png", pinned: false,
      properties: { mime: "image/png", sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", phash: "a4f891b2c3d4e5f6" }
    },
    {
      id: "img_2", entity_type: "Media", entity_id: "img_2", label: "rain_scene_a_crop.png", pinned: false,
      properties: { mime: "image/png", sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", match: "partial_region_match" }
    },
    {
      id: "img_3", entity_type: "Media", entity_id: "img_3", label: "image_with_gps.jpg", pinned: false,
      properties: { mime: "image/jpeg", exif_gps: "28.6139, 77.2090", reported_location: "Central Cultural Hall" }
    },
    {
      id: "claim_1", entity_type: "Claim", entity_id: "claim_1", label: "District Submerged Today", pinned: false,
      properties: { proposition: "Severe flash flood submerged district today", fact_check_status: "Refuted (Archive footage from 2018)" }
    },
    {
      id: "loc_1", entity_type: "Location", entity_id: "loc_1", label: "GPS 28.6139° N, 77.2090° E", pinned: false,
      properties: { precision: "exact_metadata", source: "EXIF Header", mismatch_with_claim: true }
    }
  ],
  edges: [
    {
      id: "e_1", source: "acc_1", target: "post_1", relationship: "author_of", derivation_class: "fact",
      evidence_ids: ["ev-p1"], analysis_run_id: null, statement: "Account @breaking_quick_in published post #10842 at 10:14:02Z", time_interval: null
    },
    {
      id: "e_2", source: "acc_2", target: "post_2", relationship: "author_of", derivation_class: "fact",
      evidence_ids: ["ev-p2"], analysis_run_id: null, statement: "Account @daily_wire_news published post #10843 at 10:14:05Z", time_interval: null
    },
    {
      id: "e_3", source: "acc_3", target: "post_3", relationship: "author_of", derivation_class: "fact",
      evidence_ids: ["ev-p3"], analysis_run_id: null, statement: "Account @citizen_alert_x posted response at 10:15:30Z", time_interval: null
    },
    {
      id: "e_4", source: "post_1", target: "img_1", relationship: "contains_media", derivation_class: "fact",
      evidence_ids: ["ev-img1"], analysis_run_id: null, statement: "Post contains media rain_scene_a.png", time_interval: null
    },
    {
      id: "e_5", source: "post_2", target: "img_2", relationship: "contains_media", derivation_class: "fact",
      evidence_ids: ["ev-img2"], analysis_run_id: null, statement: "Post contains cropped media variant", time_interval: null
    },
    {
      id: "e_6", source: "img_1", target: "img_2", relationship: "visual_similarity", derivation_class: "similarity",
      evidence_ids: ["ev-hash-dct"], analysis_run_id: "run-image-01",
      statement: "DCT pHash distance 2 (likely same visual source, cropped variant)", time_interval: null
    },
    {
      id: "e_7", source: "acc_1", target: "acc_2", relationship: "co_temporal_coordination", derivation_class: "hypothesis",
      evidence_ids: ["ev-timing"], analysis_run_id: "run-coord-01",
      statement: "Sub-3-second synchronized posting with identical character length and wording", time_interval: "3s"
    },
    {
      id: "e_8", source: "post_1", target: "claim_1", relationship: "asserts_claim", derivation_class: "fact",
      evidence_ids: ["ev-txt1"], analysis_run_id: null, statement: "Post explicitly claims flood submergence", time_interval: null
    },
    {
      id: "e_9", source: "post_2", target: "claim_1", relationship: "asserts_claim", derivation_class: "fact",
      evidence_ids: ["ev-txt2"], analysis_run_id: null, statement: "Post explicitly asserts identical claim", time_interval: null
    },
    {
      id: "e_10", source: "img_3", target: "loc_1", relationship: "has_metadata_location", derivation_class: "fact",
      evidence_ids: ["ev-exif"], analysis_run_id: "run-loc-01", statement: "EXIF GPS metadata embedded in image", time_interval: null
    },
    {
      id: "e_11", source: "claim_1", target: "loc_1", relationship: "location_discrepancy", derivation_class: "note",
      evidence_ids: ["ev-loc-diff"], analysis_run_id: "run-loc-01", statement: "Claimed flood zone contradicts EXIF GPS location (140km difference)", time_interval: null
    },
    {
      id: "e_12", source: "post_3", target: "post_1", relationship: "cross_references", derivation_class: "similarity",
      evidence_ids: ["ev-cross"], analysis_run_id: null, statement: "Citizen alert mentions earlier breaking post", time_interval: null
    }
  ]
};

export const DEMO_COMMENTS: CommentRow[] = [
  {
    id: "c-01", stable_id: "com-01", author_ref: "user_alpha_99", raw_text: "Ye sab fake news hai, 2018 ki purani photo circulate ho rahi hai!",
    timestamp: "2026-10-19T10:16:00Z", timestamp_precision: "second", parent_comment_id: null, permalink: "https://x.com/post/c01",
    permalink_status: "verified", review_status: "confirmed", uncertain_duplicate: false,
    analysis: {
      categories: ["debunk_refutation", "hindi_vernacular_warning"],
      spans: [{ start: 0, end: 20, term: "Ye sab fake news hai" }],
      explanation: "User flags circulation of 2018 archive material in vernacular Hindi",
      scores: { debunk_prob: 0.94, coordination_risk: 0.05 },
      validation_status: "validated", suggested_action: "corroborate_with_archive"
    }
  },
  {
    id: "c-02", stable_id: "com-02", author_ref: "bot_echo_71", raw_text: "URGENT PLEASE RETWEET FOR MAXIMUM REACH! DISASTER IN CITY!",
    timestamp: "2026-10-19T10:16:03Z", timestamp_precision: "second", parent_comment_id: null, permalink: "https://x.com/post/c02",
    permalink_status: "verified", review_status: "pending", uncertain_duplicate: true,
    analysis: {
      categories: ["coordinated_narrative", "toxic_amplification"],
      spans: [{ start: 0, end: 41, term: "URGENT PLEASE RETWEET FOR MAXIMUM REACH" }],
      explanation: "High repetition phrase matched across 14 accounts in under 60 seconds",
      scores: { debunk_prob: 0.12, coordination_risk: 0.88 },
      validation_status: "uncalibrated_rule_match", suggested_action: "flag_cluster"
    }
  },
  {
    id: "c-03", stable_id: "com-03", author_ref: "bot_echo_72", raw_text: "URGENT PLEASE RETWEET FOR MAXIMUM REACH! DISASTER IN CITY!",
    timestamp: "2026-10-19T10:16:04Z", timestamp_precision: "second", parent_comment_id: null, permalink: "https://x.com/post/c03",
    permalink_status: "verified", review_status: "pending", uncertain_duplicate: true,
    analysis: {
      categories: ["coordinated_narrative", "inauthentic_bot_pattern"],
      spans: [{ start: 0, end: 41, term: "URGENT PLEASE RETWEET FOR MAXIMUM REACH" }],
      explanation: "Duplicate verbatim text from newly registered account",
      scores: { debunk_prob: 0.10, coordination_risk: 0.92 },
      validation_status: "uncalibrated_rule_match", suggested_action: "flag_cluster"
    }
  },
  {
    id: "c-04", stable_id: "com-04", author_ref: "local_observer", raw_text: "Main abhi sector 4 mein hoon, yahan bilkul dhoop hai koi paani nahi bhara.",
    timestamp: "2026-10-19T10:17:15Z", timestamp_precision: "second", parent_comment_id: null, permalink: "https://x.com/post/c04",
    permalink_status: "verified", review_status: "confirmed", uncertain_duplicate: false,
    analysis: {
      categories: ["eyewitness_account", "counter_evidence"],
      spans: [{ start: 0, end: 35, term: "Main abhi sector 4 mein hoon" }],
      explanation: "Firsthand eyewitness refutation of claimed waterlogging",
      scores: { debunk_prob: 0.91, coordination_risk: 0.02 },
      validation_status: "validated", suggested_action: "preserve_testimony"
    }
  }
];

export const DEMO_FINDINGS: Finding[] = [
  {
    id: "f-01", question: "Did the viral flood image originate from today's weather event?",
    conclusion_category: "refuted_by_archive_match",
    evidence_ids: ["ev-img1", "ev-hash-dct"],
    excerpts: ["DCT perceptual hash match confirms identical visual structure to 2018 news story."],
    limitations: ["Color grading altered; compression artifact present in variant."],
    contradictions: [],
    review_status: "confirmed",
    review_note: "Verified by lead investigator: 2018 photo re-used to manufacture panic.",
    analysis_run_id: "run-image-01",
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: "f-02", question: "Is there evidence of coordinated inauthentic amplification between accounts?",
    conclusion_category: "probable_coordination_cluster",
    evidence_ids: ["ev-timing", "ev-txt1", "ev-txt2"],
    excerpts: ["Account @breaking_quick_in and @daily_wire_news published identical text within 3 seconds."],
    limitations: ["API rate limit prevents checking historical post frequency prior to 30 days."],
    contradictions: [],
    review_status: "pending",
    review_note: null,
    analysis_run_id: "run-coord-01",
    created_at: new Date(Date.now() - 5400000).toISOString(),
  },
  {
    id: "f-03", question: "Does image EXIF metadata match the claimed location?",
    conclusion_category: "metadata_location_discrepancy",
    evidence_ids: ["ev-exif", "ev-loc-diff"],
    excerpts: ["GPS points to a dry cultural center over 140 kilometers away from claimed disaster zone."],
    limitations: ["EXIF can be spoofed; physical inspection recommended."],
    contradictions: [],
    review_status: "confirmed",
    review_note: "Confirmed metadata mismatch.",
    analysis_run_id: "run-loc-01",
    created_at: new Date(Date.now() - 3600000).toISOString(),
  }
];

export const DEMO_JOBS: Job[] = [
  {
    id: "job-img-01", run_id: "run-image-01", kind: "image_matching", lifecycle: "completed", outcome: "success",
    stage: "done", counts: { processed: 4, matches_found: 2 }, limitations: [], warnings: [], error: null,
    cancel_requested: false, created_at: new Date(Date.now() - 7500000).toISOString(),
    started_at: new Date(Date.now() - 7490000).toISOString(), ended_at: new Date(Date.now() - 7480000).toISOString(),
    retryable: false
  },
  {
    id: "job-coord-01", run_id: "run-coord-01", kind: "coordination_detection", lifecycle: "completed", outcome: "success",
    stage: "done", counts: { accounts_analyzed: 4, clusters_flagged: 1 }, limitations: [], warnings: [], error: null,
    cancel_requested: false, created_at: new Date(Date.now() - 5600000).toISOString(),
    started_at: new Date(Date.now() - 5590000).toISOString(), ended_at: new Date(Date.now() - 5580000).toISOString(),
    retryable: false
  },
  {
    id: "job-com-01", run_id: "run-com-01", kind: "comment_analysis", lifecycle: "completed", outcome: "success",
    stage: "done", counts: { comments_scanned: 25, high_risk_held: 3 }, limitations: [], warnings: [], error: null,
    cancel_requested: false, created_at: new Date(Date.now() - 4000000).toISOString(),
    started_at: new Date(Date.now() - 3990000).toISOString(), ended_at: new Date(Date.now() - 3980000).toISOString(),
    retryable: false
  }
];

export const DEMO_CAPABILITIES: Capability[] = [
  { provider: "image_pipeline", configured: true, operations: ["dct_phash", "sliding_window_match", "exif_gps"], status: "active", detail: "Built-in deterministic pipeline" },
  { provider: "coordination_engine", configured: true, operations: ["temporal_clustering", "content_similarity"], status: "active", detail: "Multi-episode temporal rule analyzer" },
  { provider: "comment_classifier", configured: true, operations: ["multilabel_en_hi_hinglish", "span_extractor"], status: "active", detail: "Rule-based and span detection" },
  { provider: "gemini_llm", configured: false, operations: ["synthesize_narrative", "cross_lingual_reasoning"], status: "not configured", detail: "Free Gemini API key can be set in Connectors" },
  { provider: "youtube_api", configured: false, operations: ["fetch_live_comments", "channel_audit"], status: "not configured", detail: "YouTube Data API v3 key optional" },
  { provider: "google_factcheck", configured: false, operations: ["claim_review_query"], status: "not configured", detail: "Google Fact Check Tools API optional" }
];
