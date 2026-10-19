import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Case, GraphData, GraphEdge, GraphNode, Job } from "../lib/types";
import GraphCanvas from "./GraphCanvas";
import LeftPanel from "./LeftPanel";
import EvidenceDrawer from "./EvidenceDrawer";
import JobsPanel from "./JobsPanel";
import UploadBar from "./UploadBar";
import CommentsView from "./CommentsView";
import FindingsView from "./FindingsView";
import CompareView from "./CompareView";
import ExportsView from "./ExportsView";
import AgentView from "./AgentView";

type Tab = "graph" | "list" | "comments" | "findings" | "compare" | "agent" | "exports";

export default function Workspace({ caseId, initialGoal }: { caseId: string; initialGoal: string }) {
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [], truncated: false, total_nodes: 0, total_edges: 0 });
  const [tab, setTab] = useState<Tab>("graph");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [refreshToken, setRefreshToken] = useState(0);
  const [relationFilter, setRelationFilter] = useState<string[]>([]);

  const refresh = useCallback(async () => {
    const [c, g, j] = await Promise.all([
      api.getCase(caseId),
      api.graph(caseId, relationFilter.length ? relationFilter : undefined),
      api.jobs(caseId),
    ]);
    setCaseData(c);
    setGraph(g);
    setJobs(j);
  }, [caseId, relationFilter]);

  useEffect(() => { refresh(); }, [refresh, refreshToken]);

  // Poll while any job is active; SSE remains available via /events for streaming UIs.
  useEffect(() => {
    const active = jobs.some((j) => ["queued", "running"].includes(j.lifecycle));
    if (!active) return;
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [jobs, refresh]);

  const bump = () => setRefreshToken((n) => n + 1);

  return (
    <div className="workspace">
      <UploadBar caseId={caseId} caseData={caseData} initialGoal={initialGoal} onChanged={bump} />
      <div className="workspace-body">
        <LeftPanel
          caseId={caseId} graph={graph} relationFilter={relationFilter}
          onFilterChange={(rels) => { setRelationFilter(rels); setRefreshToken((n) => n + 1); }}
          onRefresh={bump}
        />
        <main style={{ minHeight: 0, display: "flex", flexDirection: "column" }}>
          <nav className="tabs" style={{ padding: "6px 10px 0", background: "var(--panel)" }}>
            {(["graph", "list", "comments", "findings", "compare", "agent", "exports"] as Tab[]).map((t) => (
              <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
                {t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </nav>
          <div style={{ flex: 1, minHeight: 0 }}>
            {tab === "graph" && (
              <GraphCanvas
                data={graph} refreshToken={refreshToken}
                onSelectNode={(n) => { setSelectedNode(n); setSelectedEdge(null); }}
                onSelectEdge={(e) => { setSelectedEdge(e); setSelectedNode(null); }}
              />
            )}
            {tab === "list" && <EntityList graph={graph} onPick={(n) => setSelectedNode(n)} />}
            {tab === "comments" && <CommentsView caseId={caseId} onChanged={bump} />}
            {tab === "findings" && <FindingsView caseId={caseId} role={caseData?.my_role || "viewer"} onChanged={bump} />}
            {tab === "compare" && <CompareView caseId={caseId} graph={graph} />}
            {tab === "agent" && <AgentView caseId={caseId} role={caseData?.my_role || "viewer"} />}
            {tab === "exports" && <ExportsView caseId={caseId} role={caseData?.my_role || "viewer"} />}
          </div>
        </main>
        <EvidenceDrawer caseId={caseId} node={selectedNode} edge={selectedEdge} onClose={() => {
          setSelectedNode(null); setSelectedEdge(null);
        }} />
      </div>
      <JobsPanel jobs={jobs} caseId={caseId} onChanged={refresh} />
    </div>
  );
}

function EntityList({ graph, onPick }: { graph: GraphData; onPick: (n: GraphNode) => void }) {
  return (
    <div className="scroll" style={{ padding: 14, height: "100%", overflow: "auto" }}>
      <p className="muted">{graph.total_nodes} entities · {graph.total_edges} relationships
        {graph.truncated && <b className="badge warn" style={{ marginLeft: 8 }}>truncated view</b>}
      </p>
      <table>
        <thead><tr><th>Type</th><th>Label</th><th>ID</th></tr></thead>
        <tbody>
          {graph.nodes.map((n) => (
            <tr key={n.id} onClick={() => onPick(n)} style={{ cursor: "pointer" }}>
              <td><span className="badge">{n.entity_type}</span></td>
              <td>{n.label}</td>
              <td className="mono muted">{n.entity_id.slice(0, 8)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
