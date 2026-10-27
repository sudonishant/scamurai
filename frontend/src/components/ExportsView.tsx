import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { CommentRow, ExportRecord } from "../lib/types";
import Icon from "./Icon";

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function ExportsView(
  { caseId, role }: { caseId: string; role: string },
) {
  const [exports, setExports] = useState<ExportRecord[]>([]);
  const [comments, setComments] = useState<CommentRow[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [fmt, setFmt] = useState("pdf");
  const [scope, setScope] = useState("all");
  const [mode, setMode] = useState("redacted");
  const [exportsLoading, setExportsLoading] = useState(true);
  const [exportsError, setExportsError] = useState("");
  const [exportsRetry, setExportsRetry] = useState(0);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentsError, setCommentsError] = useState("");
  const [commentsRetry, setCommentsRetry] = useState(0);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const canExport = ["owner", "analyst"].includes(role);

  useEffect(() => {
    let active = true;
    setExportsLoading(true);
    setExportsError("");
    api.exports(caseId)
      .then((records) => { if (active) setExports(records); })
      .catch((e: unknown) => { if (active) setExportsError(message(e)); })
      .finally(() => { if (active) setExportsLoading(false); });
    return () => { active = false; };
  }, [caseId, exportsRetry]);

  useEffect(() => {
    if (scope !== "selected") return;
    let active = true;
    setCommentsLoading(true);
    setCommentsError("");
    api.comments(caseId)
      .then((body) => { if (active) setComments(body.items); })
      .catch((e: unknown) => { if (active) setCommentsError(message(e)); })
      .finally(() => { if (active) setCommentsLoading(false); });
    return () => { active = false; };
  }, [caseId, scope, commentsRetry]);

  function toggleSelected(id: string) {
    setSelectedIds((previous) => previous.includes(id)
      ? previous.filter((selected) => selected !== id)
      : [...previous, id]);
  }

  async function create() {
    setCreating(true);
    setCreateError("");
    try {
      const created = await api.createExport(caseId, {
        fmt,
        scope,
        redaction_mode: mode,
        selected_ids: scope === "selected" ? selectedIds : [],
      });
      setExports((previous) => [created, ...previous.filter((record) => record.id !== created.id)]);
    } catch (e) {
      setCreateError(message(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="scroll" style={{ padding: 14, height: "100%", overflow: "auto" }}>
      <h3>Reports & evidence exports</h3>
      <div className="coverage">
        <b>Redacted sharing mode vs full-evidence mode.</b>
        <div className="muted" style={{ fontSize: 12 }}>
          Download links expire; flagged-only exports are explicitly not a complete list.
          Hashes support integrity but reports are not court-certified evidence.
        </div>
      </div>
      {!canExport && <p className="badge err">Your role ({role}) cannot create exports.</p>}
      <div className="row">
        <div>
          <label className="muted" htmlFor="export-format">Format</label>
          <select id="export-format" value={fmt} onChange={(e) => setFmt(e.target.value)}>
            {["pdf", "html", "csv", "json"].map((f) => <option key={f}>{f}</option>)}
          </select>
        </div>
        <div>
          <label className="muted" htmlFor="export-scope">Scope</label>
          <select id="export-scope" value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="all">all received records</option>
            <option value="selected">selected records</option>
            <option value="flagged">flagged only</option>
          </select>
        </div>
        <div>
          <label className="muted" htmlFor="export-redaction">Redaction</label>
          <select id="export-redaction" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="redacted">redacted (safe sharing)</option>
            <option value="full">full evidence (restricted)</option>
          </select>
        </div>
        <button className="btn" disabled={!canExport || creating || (scope === "selected" && selectedIds.length === 0)} onClick={create}>
          {creating ? "Generating…" : "Generate"}
        </button>
      </div>

      {scope === "selected" && <section className="coverage" aria-label="Comment record selection">
        <b>Select comments to include ({selectedIds.length} selected)</b>
        <p className="muted" style={{ fontSize: 12, margin: "5px 0 8px" }}>Selected-record exports currently include the comment records checked here.</p>
        {commentsLoading && <p className="muted" role="status">Loading comment records…</p>}
        {commentsError && <div className="inline-alert danger" role="alert"><span>{commentsError}</span><button className="btn btn-small btn-secondary" onClick={() => setCommentsRetry((value) => value + 1)}>Retry</button></div>}
        {!commentsLoading && !commentsError && comments.length === 0 && <p className="muted">No comments are available to select.</p>}
        {comments.map((comment) => <label key={comment.id} className="export-selection-item" style={{ display: "flex", gap: 8, alignItems: "flex-start", margin: "8px 0", cursor: "pointer" }}>
          <input type="checkbox" checked={selectedIds.includes(comment.id)} onChange={() => toggleSelected(comment.id)} />
          <span><b>{comment.raw_text.slice(0, 180) || "(empty comment)"}</b><small className="muted" style={{ display: "block" }}>{comment.author_ref} · {comment.id}</small></span>
        </label>)}
      </section>}
      {createError && <div className="inline-alert danger" role="alert"><Icon name="alert" /><span>{createError}</span></div>}
      {exportsLoading && <p className="muted" role="status">Loading exports…</p>}
      {exportsError && <div className="inline-alert danger" role="alert"><Icon name="alert" /><span>{exportsError}</span><button className="btn btn-small btn-secondary" onClick={() => setExportsRetry((value) => value + 1)}>Retry</button></div>}
      {!exportsLoading && !exportsError && exports.length === 0 && <p className="muted">No exports have been generated for this case.</p>}
      <table style={{ marginTop: 14 }}>
        <thead><tr><th>Format</th><th>Scope</th><th>Mode</th><th>SHA-256</th><th>Expires</th><th></th></tr></thead>
        <tbody>
          {exports.map((e) => (
            <tr key={e.id}>
              <td>{e.fmt}</td><td>{e.scope}</td><td>{e.redaction_mode}</td>
              <td className="mono muted">{e.sha256?.slice(0, 16)}…</td>
              <td className="muted">{e.expires_at ? new Date(e.expires_at).toLocaleString() : "—"}</td>
              <td>
                {e.download_url
                  ? <a href={e.download_url} target="_blank" rel="noreferrer"><button className="btn secondary">Download</button></a>
                  : <span className="badge warn">{e.status === "ready" ? "expired" : e.status}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
