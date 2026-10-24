import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Finding } from "../lib/types";

const BUCKETS: { key: string; title: string; test: (f: Finding) => boolean }[] = [
  { key: "established", title: "1 · Established (evidence-backed / accepted)",
    test: (f) => ["accepted", "confirmed"].includes(f.review_status) ||
      ["supported", "refuted", "mixed", "out_of_context"].some((category) => f.conclusion_category === category || f.conclusion_category.startsWith(`${category}_`)) ||
      f.conclusion_category.includes("exact_file") || f.conclusion_category.includes("metadata_reported") },
  { key: "signals", title: "2 · Signals & hypotheses",
    test: (f) => ["coordination", "likely", "probable", "partial", "related", "similarity", "review_candidate"]
      .some((term) => f.conclusion_category.includes(term)) },
  { key: "unknowns", title: "3 · Unknowns / insufficient evidence",
    test: (f) => ["insufficient", "not_fact", "unknown", "unavailable", "inconclusive"]
      .some((term) => f.conclusion_category.includes(term)) },
  { key: "conflicts", title: "4 · Conflicting / rejected",
    test: (f) => f.contradictions.length > 0 || f.review_status === "rejected" || f.conclusion_category.includes("conflict") },
];

const DISPLAY_BUCKETS = [
  ...BUCKETS.map(({ key, title }) => ({ key, title })),
  { key: "other", title: "5 · Other findings requiring triage" },
];

function primaryBucket(finding: Finding): string {
  if (BUCKETS[3].test(finding)) return "conflicts";
  if (BUCKETS[0].test(finding)) return "established";
  if (BUCKETS[2].test(finding)) return "unknowns";
  if (BUCKETS[1].test(finding)) return "signals";
  return "other";
}

export default function FindingsView(
  { caseId, role, refreshToken, onChanged, initialFindingId }: { caseId: string; role: string; refreshToken: number; onChanged: () => void; initialFindingId?: string },
) {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const canReview = ["owner", "reviewer"].includes(role);

  const load = useCallback(async () => {
    setError("");
    try { setFindings(await api.findings(caseId)); }
    catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [caseId]);

  useEffect(() => { setLoading(true); load(); }, [load, refreshToken]);
  useEffect(() => {
    if (initialFindingId && findings.some((row) => row.id === initialFindingId)) {
      window.setTimeout(() => document.getElementById(`finding-${initialFindingId}`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 60);
    }
  }, [initialFindingId, findings]);

  async function review(id: string, decision: string) {
    setBusyId(id);
    setError("");
    try {
      await api.reviewFinding(caseId, id, decision, "reviewed via UI");
      await load();
      onChanged();
    } catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
    finally { setBusyId(null); }
  }

  return (
    <div className="scroll" style={{ padding: 14, height: "100%", overflow: "auto" }}>
      <h3>Findings — separate questions, separate answers</h3>
      {error && <div className="inline-alert error" role="alert">{error}<button className="btn btn-secondary" onClick={load}>Retry</button></div>}
      {loading && !findings.length && <p className="muted">Loading review findings…</p>}
      {!loading && !error && !findings.length && <p className="muted">No findings yet. Run an analysis workflow or add a source observation.</p>}
      {DISPLAY_BUCKETS.map((bucket) => {
        const rows = findings.filter((finding) => primaryBucket(finding) === bucket.key);
        if (!rows.length) return null;
        return (
          <div key={bucket.key} className="findings-group">
            <h4>{bucket.title} ({rows.length})</h4>
            {rows.map((finding) => (
              <div id={`finding-${finding.id}`} key={finding.id} className={`finding-card ${initialFindingId === finding.id ? "focused-evidence" : ""}`}>
                <span className="badge">{finding.conclusion_category}</span>
                <span className="badge" style={{ marginLeft: 6 }}>review: {finding.review_status}</span>
                <p>{finding.question}</p>
                <div className="muted">evidence ids: {finding.evidence_ids.map((id) => id.slice(0, 8)).join(", ") || "none"}</div>
                {finding.limitations.map((limitation, index) => <div key={index} className="limitation">▸ {String(limitation)}</div>)}
                {canReview && (
                  <div className="pill-row" style={{ marginTop: 8 }}>
                    <button className="btn" disabled={busyId === finding.id} onClick={() => review(finding.id, "accepted")}>Accept</button>
                    <button className="btn secondary" disabled={busyId === finding.id} onClick={() => review(finding.id, "needs_more_evidence")}>Need more</button>
                    <button className="btn danger" disabled={busyId === finding.id} onClick={() => review(finding.id, "rejected")}>Reject</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
