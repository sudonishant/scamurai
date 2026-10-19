import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Finding } from "../lib/types";

const BUCKETS: { key: string; title: string; test: (f: Finding) => boolean }[] = [
  { key: "established", title: "1 · Established (evidence-backed / accepted)",
    test: (f) => f.review_status === "accepted" ||
      ["supported", "refuted", "mixed", "out_of_context"].includes(f.conclusion_category) ||
      f.conclusion_category.endsWith("exact_file") || f.conclusion_category.endsWith("metadata_reported") },
  { key: "signals", title: "2 · Signals & hypotheses",
    test: (f) => f.conclusion_category.includes("coordination:review") ||
      f.conclusion_category.includes("likely") || f.conclusion_category.includes("partial") ||
      f.conclusion_category.includes("related") },
  { key: "unknowns", title: "3 · Unknowns / insufficient evidence",
    test: (f) => f.conclusion_category.includes("insufficient") || f.conclusion_category.includes("not_fact") },
  { key: "conflicts", title: "4 · Conflicting / rejected",
    test: (f) => f.contradictions.length > 0 || f.review_status === "rejected" },
];

export default function FindingsView(
  { caseId, role, onChanged }: { caseId: string; role: string; onChanged: () => void },
) {
  const [findings, setFindings] = useState<Finding[]>([]);
  const canReview = ["owner", "reviewer"].includes(role);

  useEffect(() => { api.findings(caseId).then(setFindings); }, [caseId, findings.length]);

  async function review(id: string, decision: string) {
    await api.reviewFinding(caseId, id, decision, "reviewed via UI");
    onChanged();
  }

  return (
    <div className="scroll" style={{ padding: 14, height: "100%", overflow: "auto" }}>
      <h3>Findings — separate questions, separate answers</h3>
      {BUCKETS.map((b) => {
        const rows = findings.filter(b.test);
        if (!rows.length) return null;
        return (
          <div key={b.key} className="findings-group">
            <h4>{b.title} ({rows.length})</h4>
            {rows.map((f) => (
              <div key={f.id} className="finding-card">
                <span className="badge">{f.conclusion_category}</span>
                <span className="badge" style={{ marginLeft: 6 }}>review: {f.review_status}</span>
                <p>{f.question}</p>
                <div className="muted">evidence ids: {f.evidence_ids.map((e) => e.slice(0, 8)).join(", ") || "none"}</div>
                {f.limitations.map((l, i) => <div key={i} className="limitation">▸ {String(l)}</div>)}
                {canReview && (
                  <div className="pill-row" style={{ marginTop: 8 }}>
                    <button className="btn" onClick={() => review(f.id, "accepted")}>Accept</button>
                    <button className="btn secondary" onClick={() => review(f.id, "needs_more_evidence")}>
                      Need more
                    </button>
                    <button className="btn danger" onClick={() => review(f.id, "rejected")}>Reject</button>
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
