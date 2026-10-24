import { useEffect, useState } from "react";
import { api, mediaUrl } from "../lib/api";
import type { GraphEdge, GraphNode } from "../lib/types";

interface EvidenceMeta {
  id: string;
  source_url: string | null;
  method: string;
  object_hash: string | null;
  source_kind: string;
  note: string;
}

export default function EvidenceDrawer(
  { caseId, node, edge, onClose }:
  { caseId: string; node: GraphNode | null; edge: GraphEdge | null; onClose: () => void },
) {
  const [evidence, setEvidence] = useState<EvidenceMeta[]>([]);

  const ids = edge ? edge.evidence_ids : node ? [node.entity_id] : [];
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const found: EvidenceMeta[] = [];
      // Evidence records resolve through the evidence endpoint when the id is an evidence entity.
      if (edge) {
        for (const id of edge.evidence_ids) {
          try { found.push(await requestEvidence(caseId, id)); }
          catch { /* id may be a non-evidence entity; that's expected */ }
        }
      }
      if (!cancelled) setEvidence(found.filter(Boolean));
    }
    load();
    return () => { cancelled = true; };
  }, [caseId, edge, node]);

  if (!node && !edge) {
    return (
      <aside className="panel right">
        <h3>Evidence drawer</h3>
        <p className="muted">
          Select any node or edge to see its exact statement, source evidence, method,
          limitations and review status. A layout position never creates a relationship.
        </p>
      </aside>
    );
  }

  return (
    <aside className="panel right">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>{edge ? "Relationship" : "Entity"}</h3>
        <button className="btn secondary" onClick={onClose}>Close</button>
      </div>

      {node && (
        <div style={{ marginTop: 10 }}>
          <span className="badge">{node.entity_type}</span>
          <h4>{node.label}</h4>
          <pre className="mono">{JSON.stringify(node.properties, null, 2)}</pre>
          {node.entity_type === "media" && (
            <img src={mediaUrl(caseId, node.entity_id)} alt={node.label}
              style={{ maxWidth: "100%", borderRadius: 8, border: "1px solid var(--border)" }} />
          )}
        </div>
      )}

      {edge && (
        <div style={{ marginTop: 10 }}>
          <span className={`badge ${edge.derivation_class}`}>{edge.derivation_class}</span>
          <h4>{edge.relationship.replaceAll("_", " ")}</h4>
          <p>{edge.statement || "No statement recorded."}</p>
          <div className="evidence-chain">
            <b>How was this derived?</b>
            <div className="muted">analysis run: {edge.analysis_run_id || "source record"}</div>
            <div className="muted">time interval: {edge.time_interval || "n/a"}</div>
          </div>
          {edge.derivation_class === "hypothesis" && (
            <p className="limitation">
              Hypothesis — cannot be promoted by confident prose; requires reviewer decision.
            </p>
          )}
          {evidence.length > 0 && (
            <>
              <b>Supporting evidence records</b>
              {evidence.map((e) => (
                <div key={e.id} className="evidence-chain">
                  <div className="mono">{e.id}</div>
                  <div className="muted">{e.method} · {e.source_kind}</div>
                  {e.source_url && <a href={e.source_url} target="_blank" rel="noreferrer">{e.source_url}</a>}
                  {e.object_hash && <div className="mono muted">sha256: {e.object_hash.slice(0, 18)}…</div>}
                  {e.note && <div className="muted">{e.note}</div>}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </aside>
  );
}

async function requestEvidence(caseId: string, id: string): Promise<EvidenceMeta> {
  const token = localStorage.getItem("scamurai.devToken");
  const res = await fetch(`/api/v1/cases/${caseId}/evidence/${id}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!res.ok) throw new Error("not an evidence record");
  return res.json();
}
