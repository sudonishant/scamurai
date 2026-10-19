import type { Job } from "../lib/types";
import { api } from "../lib/api";

const LIFECYCLE_BADGE: Record<string, string> = {
  queued: "", running: "similarity", completed: "fact", failed: "err",
  cancelled: "warn", waiting_for_access: "warn", waiting_for_review: "warn",
};

export default function JobsPanel(
  { jobs, caseId, onChanged }:
  { jobs: Job[]; caseId: string; onChanged: () => void },
) {
  return (
    <section className="bottom">
      <div style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between" }}>
        <b>Jobs & timeline</b>
        <span className="muted">
          lifecycle and outcome are separate — a finished run can still be partial
        </span>
      </div>
      {jobs.length === 0 && <p className="muted" style={{ padding: "0 12px 10px" }}>No jobs yet.</p>}
      {jobs.map((j) => (
        <div key={j.id} className="job-row">
          <div><b>{j.kind}</b><div className="muted mono" style={{ fontSize: 11 }}>{j.id.slice(0, 8)}</div></div>
          <span className={`badge ${LIFECYCLE_BADGE[j.lifecycle] || ""}`}>{j.lifecycle}</span>
          <span className="badge">{j.outcome || "—"}</span>
          <div>
            <div>stage: {j.stage}</div>
            <div className="muted" style={{ fontSize: 12 }}>
              {Object.entries(j.counts).map(([k, v]) => `${k}=${v}`).join(" · ")}
            </div>
            {j.limitations.map((l, i) => <div key={i} className="limitation">⚠ {l}</div>)}
            {j.error && <div className="badge err">{j.error}</div>}
          </div>
          <button className="btn secondary" disabled={["completed", "failed", "cancelled"].includes(j.lifecycle)}
            onClick={async () => { await api.cancel(caseId, j.id); onChanged(); }}>
            Cancel
          </button>
        </div>
      ))}
    </section>
  );
}
