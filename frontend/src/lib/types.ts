export interface Case {
  id: string;
  title: string;
  purpose: string;
  allowed_sources: string[];
  date_from: string | null;
  date_to: string | null;
  languages: string[];
  retention_days: number | null;
  limits: Record<string, number>;
  my_role: string;
  created_at: string;
}

export interface GraphNode {
  id: string;
  entity_type: string;
  entity_id: string;
  label: string;
  properties: Record<string, unknown>;
  pinned: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: string;
  derivation_class: "fact" | "similarity" | "hypothesis" | "note";
  evidence_ids: string[];
  analysis_run_id: string | null;
  statement: string;
  time_interval: string | null;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
  total_nodes: number;
  total_edges: number;
}

export interface Job {
  id: string;
  run_id: string | null;
  kind: string;
  lifecycle: string;
  outcome: string | null;
  stage: string;
  counts: Record<string, number>;
  limitations: string[];
  warnings: string[];
  error: string | null;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  retryable: boolean;
}

export interface CommentAnalysis {
  categories: string[];
  spans: { start: number; end: number; term: string }[];
  explanation: string;
  scores: Record<string, number>;
  validation_status: string;
  suggested_action: string;
}

export interface CommentRow {
  id: string;
  stable_id: string | null;
  raw_text: string;
  author_ref: string;
  timestamp: string | null;
  timestamp_precision: string;
  parent_comment_id: string | null;
  permalink: string | null;
  permalink_status: string;
  review_status: string;
  uncertain_duplicate: boolean;
  analysis: CommentAnalysis | null;
}

export interface Finding {
  id: string;
  question: string;
  conclusion_category: string;
  evidence_ids: string[];
  excerpts: unknown[];
  limitations: string[];
  contradictions: unknown[];
  review_status: string;
  review_note: string | null;
  analysis_run_id: string | null;
  created_at: string;
}

export interface Capability {
  provider: string;
  configured: boolean;
  operations: string[];
  status: string;
  detail: string;
}

export interface AgentStep {
  seq: number;
  tool: string;
  ok: boolean;
  stop_reason: string | null;
  limitation: string | null;
  evidence_ids: string[];
}

export interface AgentRunResult {
  stop_reason: string;
  steps: AgentStep[];
  evidence_ids: string[];
  jobs: Job[];
}

export interface ExportRecord {
  id: string;
  fmt: string;
  scope: string;
  redaction_mode: string;
  status: string;
  sha256: string | null;
  expires_at: string | null;
  created_at: string;
  download_url: string | null;
}

export interface Narrative {
  id: string;
  label: string;
  post_count: number;
  account_count: number;
  account_ids: string[];
  evidence_post_ids: string[];
  first_observed: string | null;
  last_observed: string | null;
  undated_posts: number;
  top_terms: { term: string; count: number }[];
  bucket_size: string;
  timeline: { bucket: string | null; count: number; evidence_ids: string[] }[];
  earliest_observed: null | { post_id: string; account_id: string | null; handle: string; url: string | null; observed_at: string | null; scope: string };
  propagation: { account_id: string; handle: string; first_observed: string | null; post_id: string; role: string }[];
  representative_posts: { id: string; text: string; url: string | null; observed_at: string | null; timestamp_precision: string; handle: string }[];
  discourse_assessment: { state: string; interpretation: string };
  early_warning: null | Record<string, any>;
  locations: string[];
  analysis_scope: string;
}

export interface AnalyticsData {
  schema_version: string;
  generated_at: string;
  reference_time: string | null;
  scope: string;
  coverage: Record<string, number | boolean>;
  narratives: Narrative[];
  automation: {
    account_id: string; handle: string; platform: string; post_count: number;
    automation_indicator_score: number | null; score_type: string; evidence_coverage: number;
    status: string; features: Record<string, number | null>; triggered_indicators: string[];
    formula: string; limitations: string[]; evidence_post_ids: string[];
  }[];
  network: {
    nodes: { account_id: string; handle: string; platform: string; post_count: number; fact_link_degree: number; hypothesis_link_degree: number; observed_link_degree: number; scope: string }[];
    edges: { source_account_id: string; target_account_id: string; relationship: string; derivation_class: string; statement: string; evidence_ids: string[] }[];
    clusters: { account_ids: string[]; handles: string[]; size: number; fact_links: number; hypothesis_links: number; note: string }[];
    limitations: string[];
  };
  geospatial: {
    points: { key: string; label: string; latitude: number; longitude: number; count: number; intensity: number; anomaly: boolean }[];
    locations: Record<string, any>[];
    anomalies: Record<string, any>[];
    map_note: string;
  };
  alerts: Record<string, any>[];
  limitations: string[];
}

export interface OsintModule {
  module: "dns" | "rdap" | "web" | "certificates" | "archive" | string;
  status: string;
  data: Record<string, any> | null;
  error: { detail: string; status_code: number | null } | null;
  collected_at: string;
}

export interface OsintReport {
  id?: string;
  evidence_id?: string;
  object_hash?: string;
  schema_version: string;
  target: string;
  normalized_target: string;
  target_type: string;
  host: string;
  registrable_domain: string | null;
  status: string;
  generated_at: string;
  modules: OsintModule[];
  summary: { sources_succeeded: number; sources_total: number; sources_limited: number };
  limitations: string[];
}

export interface OsintReportSummary {
  id: string;
  target: string;
  target_type: string;
  status: string;
  summary: OsintReport["summary"];
  modules: { module: string; status: string }[];
  object_hash: string;
  created_at: string;
}

export interface MediaForensicsResult {
  id: string;
  media_asset_id: string;
  analysis_run_id: string | null;
  status: string;
  filename: string;
  sha256: string | null;
  phash: string | null;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  indicators: Record<string, any>;
  model_result: Record<string, any>;
  limitations: string[];
  created_at: string;
}
