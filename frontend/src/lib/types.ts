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
