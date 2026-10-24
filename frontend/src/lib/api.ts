// Thin typed client over the versioned /api/v1 contract with transparent offline/demo fallback.
import type {
  AgentRunResult, Capability, Case, CommentRow, ExportRecord, Finding, GraphData, Job,
} from "./types";
import {
  DEMO_USERS, DEMO_CASE, DEMO_GRAPH, DEMO_COMMENTS, DEMO_FINDINGS, DEMO_JOBS, DEMO_CAPABILITIES,
} from "./demoData";

const TOKEN_KEY = "scamurai.devToken";
const API_URL_KEY = "scamurai.apiUrl";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getApiUrl(): string {
  return localStorage.getItem(API_URL_KEY) || (import.meta as any).env?.VITE_API_BASE_URL || "";
}
export function setApiUrl(url: string) {
  localStorage.setItem(API_URL_KEY, url);
}

// In-memory demo state for when live backend is unreachable
let localCases: Case[] = [{ ...DEMO_CASE }];
let localFindings: Finding[] = [...DEMO_FINDINGS];
let localComments: CommentRow[] = [...DEMO_COMMENTS];

export class ApiError extends Error {
  status: number;
  correlationId?: string;
  constructor(status: number, message: string, correlationId?: string) {
    super(message);
    this.status = status;
    this.correlationId = correlationId;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const baseUrl = getApiUrl();
  const fullUrl = baseUrl ? `${baseUrl.replace(/\/+$/, "")}${path}` : path;

  try {
    const res = await fetch(fullUrl, {
      ...init,
      headers: {
        ...(init.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (res.ok) {
      if (res.status === 204) return undefined as T;
      return await res.json() as T;
    }
  } catch (err) {
    // Backend offline or CORS issue -> fallback to demo data below
  }

  // --- Fallback Demo Layer for Static / GitHub Pages Hosting ---
  if (path === "/api/v1/users") {
    return DEMO_USERS as unknown as T;
  }
  if (path === "/api/v1/cases" && init.method === "POST") {
    const payload = JSON.parse(String(init.body || "{}"));
    const newCase: Case = {
      id: `case-demo-${Date.now().toString(36)}`,
      title: payload.title || "Untitled investigation",
      purpose: payload.purpose || "Interactive investigation",
      allowed_sources: ["https://twitter.com", "https://youtube.com"],
      date_from: null, date_to: null,
      languages: payload.languages || ["en", "hi"],
      retention_days: 90,
      limits: { max_seed_urls: 5, max_depth: 2, max_entities: 200, max_fetches: 20 },
      my_role: "owner",
      created_at: new Date().toISOString(),
    };
    localCases = [newCase, ...localCases];
    return newCase as unknown as T;
  }
  if (path === "/api/v1/cases") {
    return localCases as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/capabilities")) {
    return DEMO_CAPABILITIES as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/audit")) {
    return [
      { action: "case_created", target_type: "case", detail: { mode: "demo" }, created_at: new Date().toISOString() },
      { action: "corpus_analyzed", target_type: "run", detail: { workflow: "coordination" }, created_at: new Date().toISOString() },
    ] as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/graph/path")) {
    return { path: ["acc_1", "post_1", "img_1", "img_2", "post_2", "acc_2"] } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/graph")) {
    return DEMO_GRAPH as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/jobs")) {
    return DEMO_JOBS as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/comments") && init.method === "POST") {
    return { ok: true } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/comments")) {
    return { total: localComments.length, coverage: [], items: localComments } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/findings") && init.method === "POST") {
    const findingId = path.split("/findings/")[1]?.split("/")[0];
    const payload = JSON.parse(String(init.body || "{}"));
    localFindings = localFindings.map(f => f.id === findingId ? { ...f, review_status: payload.decision, review_note: payload.note } : f);
    return { ok: true } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/findings")) {
    return localFindings as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/stats")) {
    return { entities: 11, relationships: 12, findings: 3, pending_reviews: 1 } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/compare")) {
    return {
      matrix: [
        { account_a: "@breaking_quick_in", account_b: "@daily_wire_news", shared_content: 2, temporal_distance: "3s", coordination_signal: "High" },
        { account_a: "@breaking_quick_in", account_b: "@citizen_alert_x", shared_content: 0, temporal_distance: "88s", coordination_signal: "Low" },
      ]
    } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/connectors/youtube/import")) {
    return {
      video_id: "demo_vid_01", comments_created: 15, uncertain_duplicates_held: 2,
      coverage: { status: "complete", unique_collected: 15, platform_displayed_count: 15 }
    } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/connectors/factcheck/search")) {
    return {
      query: "flood rain city", note: "Matches found in fact-check database",
      matches: [
        { claim: "Severe flash flood submerged district today", claimant: "Social Media Posts", outcome: "False", source: "FactCheck.org", url: "https://factcheck.org/archive" }
      ]
    } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/agent/run")) {
    return {
      stop_reason: "Goal achieved with 3 steps executed under policy boundary",
      steps: [
        { seq: 1, tool: "extract_propositions", ok: true, stop_reason: null, limitation: null, evidence_ids: ["ev-txt1"] },
        { seq: 2, tool: "query_factchecks", ok: true, stop_reason: null, limitation: null, evidence_ids: ["ev-fc1"] },
        { seq: 3, tool: "synthesize_graph_evidence", ok: true, stop_reason: null, limitation: null, evidence_ids: ["ev-graph1"] },
      ],
      evidence_ids: ["ev-txt1", "ev-fc1", "ev-graph1"],
      jobs: DEMO_JOBS,
    } as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/") && path.includes("/exports")) {
    return [
      { id: "exp-01", fmt: "pdf", scope: "full_case", redaction_mode: "none", status: "completed", sha256: "a1b2c3d4e5", expires_at: null, created_at: new Date().toISOString(), download_url: "#" }
    ] as unknown as T;
  }
  if (path.startsWith("/api/v1/cases/")) {
    const id = path.split("/api/v1/cases/")[1]?.split("/")[0];
    const found = localCases.find(c => c.id === id) || localCases[0] || DEMO_CASE;
    return found as unknown as T;
  }

  return {} as T;
}

export const api = {
  users: () => request<{ id: string; email: string; name: string; token_hint: string }[]>("/api/v1/users"),
  createCase: (body: unknown) =>
    request<Case>("/api/v1/cases", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  listCases: () => request<Case[]>("/api/v1/cases"),
  getCase: (id: string) => request<Case>(`/api/v1/cases/${id}`),
  capabilities: (id: string) => request<Capability[]>(`/api/v1/cases/${id}/capabilities`),
  audit: (id: string) =>
    request<{ action: string; target_type: string; detail: unknown; created_at: string }[]>(
      `/api/v1/cases/${id}/audit`),

  addUrlInput: (caseId: string, url: string, kind = "url") =>
    request(`/api/v1/cases/${caseId}/inputs`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, kind }),
    }),
  addTextInput: (caseId: string, text: string, language = "und") =>
    request(`/api/v1/cases/${caseId}/inputs`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }),
    }),
  upload: (caseId: string, file: File, kind: string, meta = "{}") => {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    form.append("meta", meta);
    return request(`/api/v1/cases/${caseId}/uploads`, { method: "POST", body: form });
  },

  run: (caseId: string, workflow: string, clientIdempotencyKey: string) =>
    request<{ run_id: string; job_id: string; replayed: boolean }>(
      `/api/v1/cases/${caseId}/runs`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow, client_idempotency_key: clientIdempotencyKey }),
      }),
  jobs: (caseId: string) => request<Job[]>(`/api/v1/cases/${caseId}/jobs`),
  job: (caseId: string, jobId: string) => request<Job>(`/api/v1/cases/${caseId}/jobs/${jobId}`),
  cancel: (caseId: string, jobId: string) =>
    request(`/api/v1/cases/${caseId}/jobs/${jobId}/cancel`, { method: "POST" }),
  transform: (caseId: string, body: unknown) =>
    request(`/api/v1/cases/${caseId}/transforms`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),

  graph: (caseId: string, relationTypes?: string[]) => {
    const qs = relationTypes?.length ? `?relation_types=${relationTypes.join(",")}` : "";
    return request<GraphData>(`/api/v1/cases/${caseId}/graph${qs}`);
  },
  shortestPath: (caseId: string, body: unknown) =>
    request(`/api/v1/cases/${caseId}/graph/path`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  compare: (caseId: string, accountIds: string[]) =>
    request(`/api/v1/cases/${caseId}/compare?account_ids=${accountIds.join(",")}`),

  comments: (caseId: string, q = "") =>
    request<{ total: number; coverage: unknown[]; items: CommentRow[] }>(
      `/api/v1/cases/${caseId}/comments?limit=200${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  analyzeComment: (caseId: string, commentId: string) =>
    request<CommentRow>(`/api/v1/cases/${caseId}/comments/${commentId}/analyses`, { method: "POST" }),
  findings: (caseId: string) => request<Finding[]>(`/api/v1/cases/${caseId}/findings`),
  reviewFinding: (caseId: string, findingId: string, decision: string, note: string) =>
    request(`/api/v1/cases/${caseId}/findings/${findingId}/reviews`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, note }),
    }),
  stats: (caseId: string) =>
    request<Record<string, number>>(`/api/v1/cases/${caseId}/stats`),

  youtubeImport: (caseId: string, url: string, maxPages = 3) =>
    request<{
      video_id: string;
      comments_created: number;
      uncertain_duplicates_held: number;
      coverage: { status: string; unique_collected: number; platform_displayed_count: number | null };
    }>(`/api/v1/cases/${caseId}/connectors/youtube/import`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, max_pages: maxPages }),
    }),
  factcheckSearch: (caseId: string, query: string) =>
    request<{ query: string; note: string; matches: {
      claim: string; claimant: string; outcome: string; source: string; url: string; claim_date?: string;
    }[] }>(`/api/v1/cases/${caseId}/connectors/factcheck/search`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }),
  runAgent: (caseId: string, goal: string, idempotencyKey: string) =>
    request<AgentRunResult>(`/api/v1/cases/${caseId}/agent/run`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, client_idempotency_key: idempotencyKey }),
    }),
  createExport: (caseId: string, body: unknown) =>
    request<ExportRecord>(`/api/v1/cases/${caseId}/exports`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  exports: (caseId: string) => request<ExportRecord[]>(`/api/v1/cases/${caseId}/exports`),
  registry: () => request<unknown>("/api/v1/registry"),
};

export function mediaUrl(caseId: string, mediaEntityId: string): string {
  const baseUrl = getApiUrl();
  const path = `/api/v1/cases/${caseId}/media/${mediaEntityId}/raw`;
  return baseUrl ? `${baseUrl.replace(/\/+$/, "")}${path}` : path;
}
