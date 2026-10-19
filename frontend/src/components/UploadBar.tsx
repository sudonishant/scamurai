import { useState } from "react";
import { api } from "../lib/api";
import type { Case } from "../lib/types";

const WORKFLOWS = [
  { id: "import_pipeline", label: "Fetch permitted URLs" },
  { id: "image_matching", label: "Run image pipeline" },
  { id: "comment_analysis", label: "Analyze comments" },
  { id: "coordination_detection", label: "Detect coordination" },
  { id: "claim_workflow", label: "Extract & check claims" },
  { id: "location_analysis", label: "Photo-to-location" },
];

const GOAL_HINT: Record<string, string> = {
  image_source: "image_matching",
  comments: "comment_analysis",
  coordination: "coordination_detection",
  check_post: "claim_workflow",
  photo_location: "location_analysis",
};

export default function UploadBar(
  { caseId, caseData, initialGoal, onChanged }:
  { caseId: string; caseData: Case | null; initialGoal: string; onChanged: () => void },
) {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [msg, setMsg] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const canWrite = !!caseData && ["owner", "analyst"].includes(caseData.my_role);

  async function guard(fn: () => Promise<unknown>) {
    setBusy(true); setMsg("");
    try { await fn(); onChanged(); setMsg("Done."); }
    catch (e) { setMsg(String(e)); }
    finally { setBusy(false); }
  }

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const kind = file.type.startsWith("image/") ? "image" : file.name.endsWith(".csv") ? "csv" : "json";
    await guard(() => api.upload(caseId, file, kind));
  }

  return (
    <div style={{ background: "var(--panel)", borderBottom: "1px solid var(--border)", padding: 12 }}>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div style={{ flex: 2 }}>
          <label className="muted">Post / account URL (SSRF-checked, http/https only)</label>
          <input placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
        </div>
        <button className="btn secondary" disabled={busy || !canWrite || !url}
          onClick={() => guard(() => api.addUrlInput(caseId, url))}>Add URL</button>
        <div>
          <input type="file" accept=".csv,.json,.png,.jpg,.jpeg,.gif,.webp" onChange={upload} />
        </div>
      </div>
      <div className="row" style={{ marginTop: 8, alignItems: "flex-end" }}>
        <div style={{ flex: 2 }}>
          <label className="muted">Or paste post text / claim</label>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste text…" />
        </div>
        <button className="btn secondary" disabled={busy || !canWrite || !text}
          onClick={() => guard(async () => { await api.addTextInput(caseId, text); setText(""); })}>
          Add text
        </button>
      </div>
      <div className="pill-row" style={{ marginTop: 10 }}>
        {WORKFLOWS.map((w) => (
          <button key={w.id} className="btn secondary" disabled={busy || !canWrite}
            title={GOAL_HINT[initialGoal] === w.id ? "Suggested for your selected goal" : ""}
            onClick={() => guard(() => api.run(caseId, w.id, `${w.id}-${Date.now()}`))}>
            ▶ {w.label}
          </button>
        ))}
      </div>
      {msg && <p className="muted" style={{ margin: "6px 0 0" }}>{msg}</p>}
    </div>
  );
}
