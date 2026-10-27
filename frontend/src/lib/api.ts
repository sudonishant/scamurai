import type {
  AccountDetail, AccountSummary, AgentRunResult, AlertItem, AnalyticsData, Capability, Case, CommentRow, ExportRecord, Finding,
  GraphData, Job, MediaForensicsResult, OsintReport, OsintReportSummary, SearchResponse,
} from "./types";
import { SandboxStore } from "./sandboxStore";

const TOKEN_KEY = "scamurai.devToken";
const API_URL_KEY = "scamurai.apiUrl";
const MODE_KEY = "scamurai.mode";
export const UNAUTHORIZED_EVENT = "scamurai:unauthorized";

export function isStaticDeployment(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host.includes("github.io") || host.includes("is-a.dev");
}

export function isSandboxActive(): boolean {
  return !getApiUrl() && isStaticDeployment();
}

export function getToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token === "synthetic-demo" || localStorage.getItem(MODE_KEY) === "demo") {
    [TOKEN_KEY, MODE_KEY].forEach((key) => localStorage.removeItem(key));
    return "dev-token-owner";
  }
  return token || (isStaticDeployment() ? "dev-token-owner" : null);
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
  if (stored !== null && stored !== "") return stored;
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
  let detail: string | null = null;
  let correlationId: string | undefined = undefined;
  try {
    const text = await res.text();
    // Guard against raw HTML error pages (e.g. GitHub Pages 404 or proxy error)
    if (text.trim().startsWith("<") || res.headers.get("content-type")?.includes("text/html")) {
      detail = `API endpoint returned HTTP ${res.status}. No live backend listening at this host.`;
    } else {
      const payload = text ? JSON.parse(text) : null;
      correlationId = payload?.correlation_id;
      detail = payload?.detail ?? payload?.message ?? payload?.error;
      if (Array.isArray(detail)) detail = detail.map((row: any) => row.msg || JSON.stringify(row)).join("; ");
      if (typeof detail === "object" && detail) detail = JSON.stringify(detail);
      if (!detail) detail = text.slice(0, 200);
    }
  } catch {
    /* fallback */
  }
  const message = detail || `Request failed with HTTP ${res.status}`;
  throw new ApiError(res.status, String(message), correlationId);
}

async function liveFetch(path: string, init: RequestInit = {}, timeoutMs = 90_000): Promise<Response> {
  const token = getToken();
  if (!token && !isStaticDeployment()) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new ApiError(401, "Your session has no bearer token. Sign in again with a development role or token.");
  }
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(fullUrl(path), { ...init, headers, signal: init.signal || controller.signal });
    if (res.status === 401) {
      clearAuthentication();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    if (!res.ok) await parseError(res);
    return res;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "Request timed out.");
    }
    throw new ApiError(0, "Live backend is unreachable. Check the API connection and retry.");
  } finally {
    window.clearTimeout(timeout);
  }
}

async function request<T>(path: string, init: RequestInit = {}, fallbackHandler?: () => Promise<T> | T): Promise<T> {
  if (isSandboxActive() && fallbackHandler) {
    return await fallbackHandler();
  }
}

  const res = await liveFetch(path, init);
  if (res.status === 204) return undefined as T;
  return await res.json() as T;
}

export const api = {
  users: () => request<{ id: string; email: string; name: string; token_hint: string }[]>(
    "/api/v1/users", {}, () => [
      { id: "u-owner", email: "owner@scamurai.local", name: "Case owner", token_hint: "dev-token-owner" },
      { id: "u-analyst", email: "analyst@scamurai.local", name: "Analyst", token_hint: "dev-token-analyst" },
      { id: "u-reviewer", email: "reviewer@scamurai.local", name: "Reviewer", token_hint: "dev-token-reviewer" },
      { id: "u-viewer", email: "viewer@scamurai.local", name: "Viewer", token_hint: "dev-token-viewer" },
    ]
  ),

  createCase: (body: unknown) => request<Case>(
    "/api/v1/cases",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    () => SandboxStore.createCase(body)
  ),

  listCases: () => request<Case[]>(
    "/api/v1/cases", {}, () => SandboxStore.getCases()
  ),

  getCase: (id: string) => request<Case>(
    `/api/v1/cases/${id}`, {}, () => SandboxStore.getCase(id)
  ),

  capabilities: (id: string) => request<Capability[]>(
    `/api/v1/cases/${id}/capabilities`, {}, () => SandboxStore.getCapabilities(id)
  ),

  audit: (id: string) => request<{ action: string; target_type: string; detail: unknown; created_at: string }[]>(
    `/api/v1/cases/${id}/audit`, {}, () => [
      { action: "case.create", target_type: "case", detail: { title: "Investigation scope initialized" }, created_at: new Date().toISOString() },
    ]
  ),

  addUrlInput: (caseId: string, url: string, kind = "url") => request(
    `/api/v1/cases/${caseId}/inputs`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, kind }) },
    () => ({ ok: true, id: `inp-${Date.now().toString(36)}`, url, kind })
  ),

  addTextInput: (caseId: string, text: string, language = "und") => request(
    `/api/v1/cases/${caseId}/inputs`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, language }) },
    () => ({ ok: true, id: `inp-${Date.now().toString(36)}`, text, language })
  ),

  upload: (caseId: string, file: File, kind: string, meta = "{}") => {
    const form = new FormData();
    form.append("file", file); form.append("kind", kind); form.append("meta", meta);
    return request(
      `/api/v1/cases/${caseId}/uploads`,
      { method: "POST", body: form },
      () => ({ ok: true, media_id: `m-${Date.now().toString(36)}`, filename: file.name, size: file.size })
    );
  },

  run: (caseId: string, workflow: string, clientIdempotencyKey: string) => request<{ run_id: string; job_id: string; replayed: boolean }>(
    `/api/v1/cases/${caseId}/runs`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ workflow, client_idempotency_key: clientIdempotencyKey }) },
    () => SandboxStore.runWorkflow(caseId, workflow)
  ),

  jobs: (caseId: string) => request<Job[]>(
    `/api/v1/cases/${caseId}/jobs`, {}, () => SandboxStore.getJobs(caseId)
  ),

  job: (caseId: string, jobId: string) => request<Job>(
    `/api/v1/cases/${caseId}/jobs/${jobId}`, {}, () => SandboxStore.getJobs(caseId)[0]
  ),

  cancel: (caseId: string, jobId: string) => request(
    `/api/v1/cases/${caseId}/jobs/${jobId}/cancel`,
    { method: "POST" },
    () => ({ ok: true })
  ),

  transform: (caseId: string, body: unknown) => request(
    `/api/v1/cases/${caseId}/transforms`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    () => ({ ok: true })
  ),

  graph: (caseId: string, relationTypes?: string[]) => {
    const qs = relationTypes?.length ? `?relation_types=${relationTypes.join(",")}` : "";
    return request<GraphData>(
      `/api/v1/cases/${caseId}/graph${qs}`, {}, () => SandboxStore.getGraph(caseId, relationTypes)
    );
  },

  shortestPath: (caseId: string, body: unknown) => request(
    `/api/v1/cases/${caseId}/graph/path`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    () => ({ path: ["acc_1", "post_1", "media_1"], length: 2 })
  ),

  compare: (caseId: string, accountIds: string[]) => request<{ pairs: any[]; disclaimer: string }>(
    `/api/v1/cases/${caseId}/compare?account_ids=${accountIds.join(",")}`,
    {},
    () => ({
      pairs: [
        {
          pair: accountIds.slice(0, 2),
          identity_verified: false,
          shared_content: ["Identical flood post text", "Recycled market flood image hash"],
          explicit_public_crosslinks: true,
          timing_indicators: "Broadcast within 3.2s delta across independent accounts",
          contradictory_or_insufficient: ["Platform-level device identifiers unavailable without subpoena"],
        },
      ],
      disclaimer: "Comparative analysis indicates behavioral co-occurrence only, not verified singular ownership.",
    })
  ),

  comments: (caseId: string, q = "") => request<{ total: number; coverage: unknown[]; items: CommentRow[] }>(
    `/api/v1/cases/${caseId}/comments?limit=200${q ? `&q=${encodeURIComponent(q)}` : ""}`,
    {},
    () => SandboxStore.getComments(caseId)
  ),

  analyzeComment: (caseId: string, commentId: string) => request<CommentRow>(
    `/api/v1/cases/${caseId}/comments/${commentId}/analyses`,
    { method: "POST" },
    () => SandboxStore.analyzeComment(caseId, commentId)
  ),

  evidence: <T = { id: string; source_url: string | null; method: string; object_hash: string | null; source_kind: string; note: string }>(caseId: string, evidenceId: string) => request<T>(
    `/api/v1/cases/${caseId}/evidence/${encodeURIComponent(evidenceId)}`,
    {},
    () => ({
      id: evidenceId,
      source_url: "https://public-web.org/post/10842",
      method: "hash_snapshot",
      object_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      source_kind: "social_post",
      note: "Preserved original snapshot with cryptographic verification",
    } as unknown as T)
  ),

  findings: (caseId: string) => request<Finding[]>(
    `/api/v1/cases/${caseId}/findings`, {}, () => SandboxStore.getFindings(caseId)
  ),

  reviewFinding: (caseId: string, findingId: string, decision: string, note: string) => request(
    `/api/v1/cases/${caseId}/findings/${findingId}/reviews`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, note }) },
    () => SandboxStore.reviewFinding(caseId, findingId, decision, note)
  ),

  stats: (caseId: string) => request<Record<string, number>>(
    `/api/v1/cases/${caseId}/stats`, {}, () => ({ total_posts: 42, accounts: 18, high_risk: 6, media_assets: 4 })
  ),

  youtubeImport: (caseId: string, url: string, maxPages = 3) => request<{ video_id: string; comments_created: number; uncertain_duplicates_held: number; coverage: { status: string; unique_collected: number; platform_displayed_count: number | null } }>(
    `/api/v1/cases/${caseId}/connectors/youtube/import`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, max_pages: maxPages }) },
    () => ({
      video_id: "demo_vid",
      comments_created: 15,
      uncertain_duplicates_held: 2,
      coverage: { status: "sandbox_sample", unique_collected: 15, platform_displayed_count: 17 },
    })
  ),

  mastodonImport: (caseId: string, instance: string, hashtag: string, limit = 40) => request<Record<string, any>>(
    `/api/v1/cases/${caseId}/connectors/mastodon/import`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ instance, hashtag, limit }) },
    () => ({
      posts: 14,
      accounts: 8,
      statuses_returned: 14,
      skipped_reblogs: 2,
      coverage: "Collected public hashtag preview page",
      geo_observations: 3,
    })
  ),

  factcheckSearch: (caseId: string, query: string) => request<{ query: string; note: string; matches: { claim: string; claimant: string; outcome: string; source: string; url: string; claim_date?: string }[] }>(
    `/api/v1/cases/${caseId}/connectors/factcheck/search`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) },
    () => ({
      query,
      note: "Sandbox Google Fact Check search results",
      matches: [
        {
          claim: "District completely submerged under 10ft floodwater in Oct 2026",
          claimant: "Social Media Posts",
          outcome: "False / Recycled Media",
          source: "PIB Fact Check",
          url: "https://factcheck.pib.gov.in",
          claim_date: "2026-10-23",
        },
      ],
    })
  ),

  runAgent: (caseId: string, goal: string, idempotencyKey: string) => request<AgentRunResult>(
    `/api/v1/cases/${caseId}/agent/run`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ goal, client_idempotency_key: idempotencyKey }) },
    () => ({
      stop_reason: "evidence_saturation",
      steps: [
        { seq: 1, tool: "extract_claims", ok: true, stop_reason: null, limitation: null, evidence_ids: ["ev-1"] },
        { seq: 2, tool: "detect_coordination", ok: true, stop_reason: null, limitation: null, evidence_ids: ["ev-1", "ev-2"] },
      ],
      evidence_ids: ["ev-1", "ev-2"],
      jobs: SandboxStore.getJobs(caseId),
    })
  ),

  createExport: (caseId: string, body: unknown) => request<ExportRecord>(
    `/api/v1/cases/${caseId}/exports`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    () => SandboxStore.createExport(caseId, body)
  ),

  exports: (caseId: string) => request<ExportRecord[]>(
    `/api/v1/cases/${caseId}/exports`,
    {},
    () => [SandboxStore.createExport(caseId, {})]
  ),

  registry: () => request<unknown>(
    "/api/v1/registry",
    {},
    () => ({ providers: ["youtube", "reddit", "mastodon", "factcheck"] })
  ),

  analytics: (caseId: string) => request<AnalyticsData>(
    `/api/v1/cases/${caseId}/analytics`,
    {},
    () => SandboxStore.getAnalytics(caseId)
  ),

  accounts: (caseId: string, q = "") => request<AccountSummary[]>(
    `/api/v1/cases/${caseId}/accounts${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    {},
    () => [
      { id: "acc_1", handle: "@flood_alert_rapid", display_name: "Rapid Flood News", platform: "twitter_like", post_count: 14, canonical_profile_url: null, identity_confirmed: false, last_source_timestamp: "2026-10-23T10:14:02Z", last_collected_at: new Date().toISOString() },
      { id: "acc_2", handle: "@daily_wire_express", display_name: "Daily Wire Express", platform: "twitter_like", post_count: 12, canonical_profile_url: null, identity_confirmed: false, last_source_timestamp: "2026-10-23T10:14:05Z", last_collected_at: new Date().toISOString() },
      { id: "acc_3", handle: "@citizen_voice_in", display_name: "Citizen Voice", platform: "twitter_like", post_count: 6, canonical_profile_url: null, identity_confirmed: false, last_source_timestamp: "2026-10-23T10:15:30Z", last_collected_at: new Date().toISOString() },
    ]
  ),

  accountDetail: (caseId: string, accountId: string) => request<AccountDetail>(
    `/api/v1/cases/${caseId}/accounts/${encodeURIComponent(accountId)}`,
    {},
    () => ({
      id: accountId,
      handle: accountId === "acc_2" ? "@daily_wire_express" : "@flood_alert_rapid",
      platform: "twitter_like",
      post_count: 14,
      automation_score: 0.89,
      behavioral_indicators: ["Fixed-interval burst posting", "Near-100% duplicate textual payload"],
      first_observed: "2026-10-23T10:14:02Z",
      last_observed: "2026-10-24T18:22:00Z",
    } as any)
  ),

  alerts: (caseId: string, active?: boolean) => request<AlertItem[]>(
    `/api/v1/cases/${caseId}/alerts${active === undefined ? "" : `?active=${active}`}`,
    {},
    () => [
      { id: "alt-1", type: "coordination_surge", title: "Coordinated Narrative Surge Detected", severity: "high", description: "Identical text broadcast across 2 accounts within 3 seconds linking to newly registered domain.", status: "active", created_at: new Date().toISOString() } as any,
    ]
  ),

  reviewAlert: (caseId: string, alertId: string, status: string, note: string) => request<AlertItem>(
    `/api/v1/cases/${caseId}/alerts/${encodeURIComponent(alertId)}/review`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status, note }) },
    () => ({ id: alertId, status, review_note: note } as any)
  ),

  search: (caseId: string, query: string) => request<SearchResponse>(
    `/api/v1/cases/${caseId}/search?q=${encodeURIComponent(query)}`,
    {},
    () => ({
      query,
      results: [
        { id: "post_1", kind: "post", title: "Post #10842 (Breaking Floods)", snippet: "URGENT: Entire district submerged in unexpected floods! Authorities missing." },
        { id: "media_1", kind: "media", title: "flood_submerged_market.png", snippet: "Recycled photograph from August 2021" },
      ],
      total: 2,
    } as any)
  ),

  investigateOsint: (caseId: string, target: string, modules?: string[]) => {
    if (isSandboxActive()) {
      return Promise.reject(new ApiError(503, "Live OSINT collection is disabled in the synthetic browser preview. Configure a live backend for source-attributed observations."));
    }
    return request<OsintReport>(
      `/api/v1/cases/${caseId}/osint/investigate`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target, modules }) }
    );
  },

  osintReports: (caseId: string) => request<OsintReportSummary[]>(
    `/api/v1/cases/${caseId}/osint/reports`,
    {},
    () => SandboxStore.getOsintReports(caseId)
  ),

  osintReport: (caseId: string, reportId: string) => request<OsintReport>(
    `/api/v1/cases/${caseId}/osint/reports/${reportId}`,
    {},
    () => SandboxStore.getOsintReport(caseId, reportId)
  ),

  mediaForensics: (caseId: string) => request<MediaForensicsResult[]>(
    `/api/v1/cases/${caseId}/media/forensics`,
    {},
    () => SandboxStore.getMediaForensics(caseId)
  ),
};

export async function authorizedMediaObjectUrl(caseId: string, mediaEntityId: string): Promise<string> {
  if (isSandboxActive()) {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 360;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#0c1524";
      ctx.fillRect(0, 0, 640, 360);
      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 20px monospace";
      ctx.fillText(`SCAMURAI EVIDENCE PREVIEW [${mediaEntityId}]`, 30, 180);
      ctx.font = "14px monospace";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("Cryptographic hash: e3b0c44298fc1c149afbf4c8996fb92427ae...", 30, 220);
    }
    return canvas.toDataURL("image/png");
  }
  const res = await liveFetch(`/api/v1/cases/${caseId}/media/${mediaEntityId}/raw`, {}, 30_000);
  return URL.createObjectURL(await res.blob());
}

export async function downloadOsintReport(caseId: string, reportId: string): Promise<void> {
  let blob: Blob;
  if (isSandboxActive()) {
    const report = SandboxStore.getOsintReport(caseId, reportId);
    blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  } else {
    const res = await liveFetch(`/api/v1/cases/${caseId}/osint/reports/${reportId}/download`, {}, 30_000);
    blob = await res.blob();
  }
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `scamurai-osint-${reportId.slice(0, 8)}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}
