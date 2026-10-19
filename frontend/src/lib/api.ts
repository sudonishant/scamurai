// Thin typed client over the versioned /api/v1 contract. Never stores secrets;
// the dev token is a clearly-labeled local development convenience.
import type {
  AgentRunResult, Capability, Case, CommentRow, ExportRecord, Finding, GraphData, Job,
} from "./types";

const TOKEN_KEY = "ps03.devToken";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

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
  const res = await fetch(path, {
    ...init,
    headers: {
      ...(init.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    let correlationId: string | undefined;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body);
      correlationId = body.correlation_id;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail, correlationId);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
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
  return `/api/v1/cases/${caseId}/media/${mediaEntityId}/raw`;
}
