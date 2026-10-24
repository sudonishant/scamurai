// Live-only typed API client. Every result comes from FastAPI; there is no demo-data path.
import type {
  AgentRunResult, AnalyticsData, Capability, Case, CommentRow, ExportRecord, Finding,
  GraphData, Job, MediaForensicsResult, OsintReport, OsintReportSummary,
} from "./types";

const TOKEN_KEY = "scamurai.devToken";
const API_URL_KEY = "scamurai.apiUrl";
const MODE_KEY = "scamurai.mode"; // legacy key is recognized only to clear old sessions
export const UNAUTHORIZED_EVENT = "scamurai:unauthorized";

export function getToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token === "synthetic-demo" || localStorage.getItem(MODE_KEY) === "demo") {
    [TOKEN_KEY, MODE_KEY].forEach((key) => localStorage.removeItem(key));
    return null;
  }
  localStorage.removeItem(MODE_KEY);
  return token;
}

export function setToken(token: string) {
  const clean = token.trim().replace(/^Bearer\s+/i, "");
  if (clean) localStorage.setItem(TOKEN_KEY, clean);
  else localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(MODE_KEY);
}

function clearAuthentication() {
  [TOKEN_KEY, MODE_KEY].forEach((key) => localStorage.removeItem(key));
}

export function clearSession() {
  clearAuthentication();
}

export function getApiUrl(): string {
  const stored = localStorage.getItem(API_URL_KEY);
  if (stored !== null) return stored; // an explicit empty value means same-origin
  return (import.meta as any).env?.VITE_API_BASE_URL || "";
}

export function setApiUrl(url: string): string {
  const value = url.trim();
  if (!value) {
    localStorage.setItem(API_URL_KEY, "");
    return "";
  }
  let parsed: URL;
  try { parsed = new URL(value); }
  catch { throw new Error("Enter a complete FastAPI base URL, for example https://api.example.org."); }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("The FastAPI base URL must use HTTP or HTTPS.");
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("Use a base URL without credentials, query parameters or fragments.");
  }
  if (window.location.protocol === "https:" && parsed.protocol !== "https:") {
    throw new Error("An HTTPS-hosted UI requires an HTTPS FastAPI URL to avoid mixed-content blocking.");
  }
  const clean = parsed.toString().replace(/\/+$/, "");
  localStorage.setItem(API_URL_KEY, clean);
  return clean;
}

export class ApiError extends Error {
  status: number;
  correlationId?: string;
  constructor(status: number, message: string, correlationId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.correlationId = correlationId;
  }
}

function fullUrl(path: string): string {
  const baseUrl = getApiUrl();
  return baseUrl ? `${baseUrl.replace(/\/+$/, "")}${path}` : path;
}

async function parseError(res: Response): Promise<never> {
  const text = await res.text();
  let payload: any = null;
  try { payload = text ? JSON.parse(text) : null; } catch { /* plain-text upstream error */ }
  let detail = payload?.detail ?? payload?.message ?? payload?.error;
  if (Array.isArray(detail)) detail = detail.map((row) => row.msg || JSON.stringify(row)).join("; ");
  if (typeof detail === "object" && detail) detail = JSON.stringify(detail);
  const message = detail || text.slice(0, 300) || `Request failed with HTTP ${res.status}`;
  throw new ApiError(res.status, String(message), payload?.correlation_id);
}

async function liveFetch(path: string, init: RequestInit = {}, timeoutMs = 90_000): Promise<Response> {
  const token = getToken();
  if (!token) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new ApiError(401, "Your session has no bearer token. Sign in again with a development role or token.");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(fullUrl(path), { ...init, headers, signal: init.signal || controller.signal });
    if (res.status === 401) {
      // Authentication expired; keep the explicitly configured backend connection.
      clearAuthentication();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    if (!res.ok) await parseError(res);
    return res;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "Request timed out. The source may be slow; no partial browser-side result was invented.");
    }
    throw new ApiError(0, "Live backend is unreachable. Check the API connection and retry.");
  } finally {
    window.clearTimeout(timeout);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await liveFetch(path, init);
  if (res.status === 204) return undefined as T;
  return await res.json() as T;
}

export const api = {
  users: () => request<{ id: string; email: string; name: string; role_hint: string }[]>("/api/v1/users"),
  createCase: (body: unknown) => request<Case>("/api/v1/cases", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  listCases: () => request<Case[]>("/api/v1/cases"),
  getCase: (id: string) => request<Case>(`/api/v1/cases/${id}`),
  capabilities: (id: string) => request<Capability[]>(`/api/v1/cases/${id}/capabilities`),
  audit: (id: string) => request<{ action: string; target_type: string; detail: unknown; created_at: string }[]>(`/api/v1/cases/${id}/audit`),
  addUrlInput: (caseId: string, url: string, kind = "url") => request(`/api/v1/cases/${caseId}/inputs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, kind }) }),
  addTextInput: (caseId: string, text: string, language = "und") => request(`/api/v1/cases/${caseId}/inputs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, language }) }),
  upload: (caseId: string, file: File, kind: string, meta = "{}") => {
    const form = new FormData();
    form.append("file", file); form.append("kind", kind); form.append("meta", meta);
    return request(`/api/v1/cases/${caseId}/uploads`, { method: "POST", body: form });
  },
  run: (caseId: string, workflow: string, clientIdempotencyKey: string) => request<{ run_id: string; job_id: string; replayed: boolean }>(`/api/v1/cases/${caseId}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ workflow, client_idempotency_key: clientIdempotencyKey }) }),
  jobs: (caseId: string) => request<Job[]>(`/api/v1/cases/${caseId}/jobs`),
  job: (caseId: string, jobId: string) => request<Job>(`/api/v1/cases/${caseId}/jobs/${jobId}`),
  cancel: (caseId: string, jobId: string) => request(`/api/v1/cases/${caseId}/jobs/${jobId}/cancel`, { method: "POST" }),
  transform: (caseId: string, body: unknown) => request(`/api/v1/cases/${caseId}/transforms`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  graph: (caseId: string, relationTypes?: string[]) => {
    const qs = relationTypes?.length ? `?relation_types=${relationTypes.join(",")}` : "";
    return request<GraphData>(`/api/v1/cases/${caseId}/graph${qs}`);
  },
  shortestPath: (caseId: string, body: unknown) => request(`/api/v1/cases/${caseId}/graph/path`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  compare: (caseId: string, accountIds: string[]) => request(`/api/v1/cases/${caseId}/compare?account_ids=${accountIds.join(",")}`),
  comments: (caseId: string, q = "") => request<{ total: number; coverage: unknown[]; items: CommentRow[] }>(`/api/v1/cases/${caseId}/comments?limit=200${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  analyzeComment: (caseId: string, commentId: string) => request<CommentRow>(`/api/v1/cases/${caseId}/comments/${commentId}/analyses`, { method: "POST" }),
  evidence: <T = { id: string; source_url: string | null; method: string; object_hash: string | null; source_kind: string; note: string }>(caseId: string, evidenceId: string) => request<T>(`/api/v1/cases/${caseId}/evidence/${encodeURIComponent(evidenceId)}`),
  findings: (caseId: string) => request<Finding[]>(`/api/v1/cases/${caseId}/findings`),
  reviewFinding: (caseId: string, findingId: string, decision: string, note: string) => request(`/api/v1/cases/${caseId}/findings/${findingId}/reviews`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, note }) }),
  stats: (caseId: string) => request<Record<string, number>>(`/api/v1/cases/${caseId}/stats`),
  youtubeImport: (caseId: string, url: string, maxPages = 3) => request<{ video_id: string; comments_created: number; uncertain_duplicates_held: number; coverage: { status: string; unique_collected: number; platform_displayed_count: number | null } }>(`/api/v1/cases/${caseId}/connectors/youtube/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, max_pages: maxPages }) }),
  mastodonImport: (caseId: string, instance: string, hashtag: string, limit = 40) => request<Record<string, any>>(`/api/v1/cases/${caseId}/connectors/mastodon/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ instance, hashtag, limit }) }),
  factcheckSearch: (caseId: string, query: string) => request<{ query: string; note: string; matches: { claim: string; claimant: string; outcome: string; source: string; url: string; claim_date?: string }[] }>(`/api/v1/cases/${caseId}/connectors/factcheck/search`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) }),
  runAgent: (caseId: string, goal: string, idempotencyKey: string) => request<AgentRunResult>(`/api/v1/cases/${caseId}/agent/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ goal, client_idempotency_key: idempotencyKey }) }),
  createExport: (caseId: string, body: unknown) => request<ExportRecord>(`/api/v1/cases/${caseId}/exports`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  exports: (caseId: string) => request<ExportRecord[]>(`/api/v1/cases/${caseId}/exports`),
  registry: () => request<unknown>("/api/v1/registry"),
  analytics: (caseId: string) => request<AnalyticsData>(`/api/v1/cases/${caseId}/analytics`),
  investigateOsint: (caseId: string, target: string, modules?: string[]) => request<OsintReport>(`/api/v1/cases/${caseId}/osint/investigate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target, modules }) }),
  osintReports: (caseId: string) => request<OsintReportSummary[]>(`/api/v1/cases/${caseId}/osint/reports`),
  osintReport: (caseId: string, reportId: string) => request<OsintReport>(`/api/v1/cases/${caseId}/osint/reports/${reportId}`),
  mediaForensics: (caseId: string) => request<MediaForensicsResult[]>(`/api/v1/cases/${caseId}/media/forensics`),
};

export async function authorizedMediaObjectUrl(caseId: string, mediaEntityId: string): Promise<string> {
  const res = await liveFetch(`/api/v1/cases/${caseId}/media/${mediaEntityId}/raw`, {}, 30_000);
  return URL.createObjectURL(await res.blob());
}

export async function downloadOsintReport(caseId: string, reportId: string): Promise<void> {
  const res = await liveFetch(`/api/v1/cases/${caseId}/osint/reports/${reportId}/download`, {}, 30_000);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `scamurai-osint-${reportId.slice(0, 8)}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}
