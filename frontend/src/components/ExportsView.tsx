import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { ExportRecord } from "../lib/types";

export default function ExportsView(
  { caseId, role }: { caseId: string; role: string },
) {
  const [exports, setExports] = useState<ExportRecord[]>([]);
  const [fmt, setFmt] = useState("pdf");
  const [scope, setScope] = useState("all");
  const [mode, setMode] = useState("redacted");
  const canExport = ["owner", "analyst"].includes(role);

  async function load() { setExports(await api.exports(caseId)); }
  useEffect(() => { load(); }, [caseId]);

  async function create() {
    await api.createExport(caseId, { fmt, scope, redaction_mode: mode, selected_ids: [] });
    load();
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
          <label className="muted">Format</label>
          <select value={fmt} onChange={(e) => setFmt(e.target.value)}>
            {["pdf", "html", "csv", "json"].map((f) => <option key={f}>{f}</option>)}
          </select>
        </div>
        <div>
          <label className="muted">Scope</label>
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="all">all received records</option>
            <option value="selected">selected records</option>
            <option value="flagged">flagged only</option>
          </select>
        </div>
        <div>
          <label className="muted">Redaction</label>
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="redacted">redacted (safe sharing)</option>
            <option value="full">full evidence (restricted)</option>
          </select>
        </div>
        <button className="btn" disabled={!canExport} onClick={create}>Generate</button>
      </div>
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
                  : <span className="badge warn">expired</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
