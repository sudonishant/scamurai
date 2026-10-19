import { useState } from "react";
import { api } from "../lib/api";
import type { AgentStep } from "../lib/types";

const GOALS = [
  { id: "check_post", label: "Check a post", hint: "claims + approved search planning" },
  { id: "image_source", label: "Find image source", hint: "exact/visual matches, OCR only if provider enabled" },
  { id: "photo_location", label: "Estimate photo location", hint: "stops honestly without a vision provider" },
  { id: "comments", label: "Analyze comments", hint: "bounded contextual analysis" },
  { id: "coordination", label: "Investigate coordination", hint: "repeated-alignment features" },
];

export default function AgentView({ caseId, role }: { caseId: string; role: string }) {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [stopReason, setStopReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const canRun = ["owner", "analyst"].includes(role);

  async function run(goal: string) {
    setBusy(true); setError(""); setSteps([]); setStopReason("");
    try {
      const body = await api.runAgent(caseId, goal, `agent-${goal}-${Date.now()}`);
      setSteps(body.steps);
      setStopReason(body.stop_reason);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="scroll" style={{ padding: 14, height: "100%", overflow: "auto" }}>
      <h3>Controlled investigation agent</h3>
      <p className="muted">
        Deterministic plan → policy validation → allowlisted tools → evidence. The agent has no shell,
        no arbitrary SQL, no cross-case access, and cannot publish or message anyone. External-provider
        steps stop honestly instead of fabricating evidence.
      </p>
      {!canRun && <p className="badge err">Your role ({role}) cannot run the agent.</p>}
      <div className="pill-row">
        {GOALS.map((g) => (
          <button key={g.id} className="btn secondary" disabled={busy || !canRun} title={g.hint}
            onClick={() => run(g.id)}>
            {busy ? "…" : "▸"} {g.label}
          </button>
        ))}
      </div>
      {error && <p className="badge err">{error}</p>}
      {stopReason && (
        <div className="coverage">
          <b>Stop reason:</b> <span className="badge warn">{stopReason}</span>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            Every stop is explicit — budget, deadline, policy denial or completion.
          </div>
        </div>
      )}
      {steps.map((s) => (
        <div key={s.seq} className="finding-card">
          <div>
            <span className="badge">{s.seq}</span> <b>{s.tool}</b>{" "}
            <span className={`badge ${s.ok ? "fact" : "err"}`}>{s.ok ? "executed" : "stopped"}</span>
            {s.stop_reason && <span className="badge warn" style={{ marginLeft: 6 }}>{s.stop_reason}</span>}
          </div>
          {s.limitation && <div className="limitation">▸ {s.limitation}</div>}
          {s.evidence_ids.length > 0 && (
            <div className="muted mono" style={{ fontSize: 12 }}>evidence: {s.evidence_ids.join(", ")}</div>
          )}
        </div>
      ))}
    </div>
  );
}
