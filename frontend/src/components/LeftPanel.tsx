import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Capability, GraphData } from "../lib/types";

const RELATION_CLASSES = [
  "PUBLISHED", "REPLIES_TO", "CONTAINS_MEDIA", "EXACT_FILE_MATCH", "VISUAL_SOURCE_MATCH",
  "SEMANTICALLY_SIMILAR", "PUBLICLY_CROSSLINKS", "POSSIBLY_COORDINATED_WITH",
  "GPS_METADATA_REPORTS", "POSSIBLY_DEPICTS", "ASSERTS_CLAIM", "PRESERVED_AS",
];

export default function LeftPanel(
  { caseId, graph, relationFilter, onFilterChange, onRefresh }:
  { caseId: string; graph: GraphData; relationFilter: string[];
    onFilterChange: (rels: string[]) => void; onRefresh: () => void },
) {
  const [caps, setCaps] = useState<Capability[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});

  useEffect(() => {
    api.capabilities(caseId).then(setCaps).catch(() => setCaps([]));
    api.stats(caseId).then(setStats).catch(() => setStats({}));
  }, [caseId, graph.total_nodes]);

  const present = new Set(graph.edges.map((e) => e.relationship));

  return (
    <aside className="panel">
      <h3>Case navigator</h3>
      <div className="coverage">
        {Object.entries(stats).map(([k, v]) => (
          <div key={k} className="muted">{k}: <b>{v}</b></div>
        ))}
      </div>

      <h4>Filter relationships</h4>
      <div className="pill-row">
        {RELATION_CLASSES.filter((r) => present.has(r)).map((r) => (
          <button key={r}
            className={`badge ${relationFilter.includes(r) ? "similarity" : ""}`}
            onClick={() => onFilterChange(
              relationFilter.includes(r)
                ? relationFilter.filter((x) => x !== r)
                : [...relationFilter, r])}>
            {r.replaceAll("_", " ")}
          </button>
        ))}
        {relationFilter.length > 0 && (
          <button className="badge err" onClick={() => onFilterChange([])}>clear</button>
        )}
      </div>

      <h4>Connector capabilities</h4>
      {caps.map((c) => (
        <div key={c.provider} className="evidence-chain">
          <div><b>{c.provider}</b> <span className={`badge ${c.configured ? "fact" : "warn"}`}>{c.status}</span></div>
          <div className="muted" style={{ fontSize: 12 }}>{c.detail}</div>
        </div>
      ))}
      <button className="btn secondary" style={{ width: "100%", marginTop: 8 }} onClick={onRefresh}>
        Refresh graph
      </button>
    </aside>
  );
}
