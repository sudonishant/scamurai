import { useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Case } from "../lib/types";
import Icon from "./Icon";

const WORKFLOWS = [
  { id: "import_pipeline", label: "Fetch permitted URLs", icon: "link" },
  { id: "image_matching", label: "Match image variants", icon: "media" },
  { id: "media_forensics", label: "Media forensics", icon: "shield" },
  { id: "comment_analysis", label: "Analyze comments", icon: "narrative" },
  { id: "coordination_detection", label: "Coordination features", icon: "users" },
  { id: "claim_workflow", label: "Extract & check claims", icon: "check" },
  { id: "location_analysis", label: "Photo location evidence", icon: "map" },
];
const GOAL_HINT: Record<string, string> = { media: "media_forensics", comments: "comment_analysis", coordination: "coordination_detection", check_post: "claim_workflow", photo_location: "location_analysis" };

export default function UploadBar({ caseId, caseData, initialGoal, onChanged, onClose }: { caseId: string; caseData: Case | null; initialGoal: string; onChanged: () => void; onClose?: () => void }) {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const canWrite = !!caseData && ["owner", "analyst"].includes(caseData.my_role);

  async function guard(key: string, fn: () => Promise<unknown>, success: string) {
    setBusy(key); setMessage(""); setError("");
    try { await fn(); onChanged(); setMessage(success); }
    catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
    finally { setBusy(""); }
  }
  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const kind = file.type.startsWith("image/") ? "image" : file.name.toLowerCase().endsWith(".csv") ? "csv" : "json";
    await guard("upload", () => api.upload(caseId, file, kind), `${file.name} uploaded and validated.`);
    e.target.value = "";
  }

  return <section className="collector-panel">
    <div className="collector-head"><div><span className="eyebrow">AUTHORIZED COLLECTION</span><h2>Add evidence & run workflows</h2></div>{onClose && <button className="icon-button" onClick={onClose}><Icon name="close" /></button>}</div>
    <div className="collector-grid">
      <div className="collector-block"><label><Icon name="link" size={15} /> Public post / account URL</label><div className="inline-form"><input placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} disabled={!canWrite || !!busy} /><button className="btn btn-secondary" disabled={!canWrite || !!busy || !url.trim()} onClick={() => guard("url", async () => { await api.addUrlInput(caseId, url.trim()); setUrl(""); }, "URL added after public-target preflight.")}>{busy === "url" ? "Adding…" : "Add URL"}</button></div><small>HTTP(S) only · non-public destinations blocked · platform access rules still apply</small></div>
      <div className="collector-block"><label><Icon name="narrative" size={15} /> Paste post text / claim</label><div className="inline-form"><input value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste source text…" disabled={!canWrite || !!busy} /><button className="btn btn-secondary" disabled={!canWrite || !!busy || !text.trim()} onClick={() => guard("text", async () => { await api.addTextInput(caseId, text.trim()); setText(""); }, "Manual text evidence added.")}>{busy === "text" ? "Adding…" : "Add text"}</button></div><small>Manual entry is labelled as such; it is not represented as a platform record</small></div>
      <div className="collector-block upload-block"><label><Icon name="upload" size={15} /> Authorized file import</label><label className={`file-drop ${!canWrite ? "disabled" : ""}`}><input type="file" accept=".csv,.json,.png,.jpg,.jpeg,.gif,.webp" onChange={upload} disabled={!canWrite || !!busy} /><Icon name="upload" /><span><b>{busy === "upload" ? "Validating upload…" : "Choose JSON, CSV or image"}</b><small>Signature & size checked · original bytes preserved</small></span></label><details><summary>Posts JSON geo fields</summary><code>location: {"{ name, latitude, longitude, precision }"}</code></details></div>
    </div>
    <div className="workflow-row"><span className="workflow-label">RUN</span>{WORKFLOWS.map((workflow) => <button key={workflow.id} className={`workflow-button ${GOAL_HINT[initialGoal] === workflow.id ? "suggested" : ""}`} disabled={!canWrite || !!busy} title={GOAL_HINT[initialGoal] === workflow.id ? "Suggested for your selected goal" : workflow.label} onClick={() => guard(workflow.id, () => api.run(caseId, workflow.id, `${workflow.id}-${Date.now()}`), `${workflow.label} job queued.`)}><Icon name={workflow.icon} size={14} />{busy === workflow.id ? "Queueing…" : workflow.label}</button>)}</div>
    {!canWrite && <p className="limitation">Your {caseData?.my_role || "current"} role is read-only for collection and workflows.</p>}
    {message && <div className="inline-alert success"><Icon name="check" />{message}</div>}{error && <div className="inline-alert danger"><Icon name="alert" />{error}</div>}
  </section>;
}
