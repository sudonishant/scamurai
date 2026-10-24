import { useEffect, useState } from "react";
import { api, authorizedMediaObjectUrl } from "../lib/api";
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
  const [failedEvidenceIds, setFailedEvidenceIds] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    setEvidence([]);
    setFailedEvidenceIds([]);
    async function load() {
      if (!edge?.evidence_ids.length) return;
      const results = await Promise.allSettled(edge.evidence_ids.map((id) => api.evidence<EvidenceMeta>(caseId, id)));
      if (cancelled) return;
      setEvidence(results.flatMap((result) => result.status === "fulfilled" ? [result.value] : []));
      setFailedEvidenceIds(edge.evidence_ids.filter((_, index) => results[index].status === "rejected"));
    }
    load();
    return () => { cancelled = true; };
  }, [caseId, edge]);

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
          {node.entity_type === "media" && <AuthorizedMediaPreview caseId={caseId} mediaId={node.entity_id} label={node.label} />}
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
            <p className="limitation">Hypothesis — cannot be promoted by confident prose; requires reviewer decision.</p>
          )}
          {failedEvidenceIds.length > 0 && (
            <p className="limitation">Could not load {failedEvidenceIds.length} referenced evidence record(s). Missing detail is not treated as absent evidence.</p>
          )}
          {evidence.length > 0 && (
            <>
              <b>Supporting evidence records</b>
              {evidence.map((item) => (
                <div key={item.id} className="evidence-chain">
                  <div className="mono">{item.id}</div>
                  <div className="muted">{item.method} · {item.source_kind}</div>
                  {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">{item.source_url}</a>}
                  {item.object_hash && <div className="mono muted">sha256: {item.object_hash.slice(0, 18)}…</div>}
                  {item.note && <div className="muted">{item.note}</div>}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </aside>
  );
}

function AuthorizedMediaPreview({ caseId, mediaId, label }: { caseId: string; mediaId: string; label: string }) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setUrl("");
    setFailed(false);
    authorizedMediaObjectUrl(caseId, mediaId).then((value) => {
      if (!active) { if (value) URL.revokeObjectURL(value); return; }
      objectUrl = value;
      setUrl(value);
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [caseId, mediaId]);
  if (url) return <img src={url} alt={label} style={{ maxWidth: "100%", borderRadius: 8, border: "1px solid var(--border)" }} />;
  return <p className="muted">{failed ? "Authorized media preview could not be loaded." : "Loading authorized media preview…"}</p>;
}
