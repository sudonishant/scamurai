import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { AnalyticsData, Case, GraphData, GraphEdge, GraphNode, Job } from "../lib/types";
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
import ConnectorsView from "./ConnectorsView";
import OverviewView from "./OverviewView";
import NarrativesView from "./NarrativesView";
import NetworkView from "./NetworkView";
import GeoView from "./GeoView";
import OsintView from "./OsintView";
import MediaView from "./MediaView";
import AlertsView from "./AlertsView";
import AccountsView from "./AccountsView";
import GlobalSearch from "./GlobalSearch";
import Icon from "./Icon";

type Tab = "overview" | "alerts" | "narratives" | "geo" | "osint" | "accounts" | "network" | "graph" | "entities" | "media" | "comments" | "findings" | "compare" | "exports" | "connectors" | "agent";
interface Focus { account?: string; alert?: string; post?: string; finding?: string; evidence?: string; [key: string]: string | undefined }
const TAB_IDS: Tab[] = ["overview", "alerts", "narratives", "geo", "osint", "accounts", "network", "graph", "entities", "media", "comments", "findings", "compare", "exports", "connectors", "agent"];
const FOCUS_KEYS = ["account", "alert", "post", "finding", "evidence"];
const NAV_GROUPS: { label: string; items: { id: Tab; label: string; icon: string }[] }[] = [
  { label: "Monitor", items: [{ id: "overview", label: "Overview", icon: "activity" }, { id: "alerts", label: "Alerts", icon: "alert" }, { id: "narratives", label: "Narratives", icon: "narrative" }, { id: "geo", label: "Geospatial", icon: "map" }] },
  { label: "Investigate", items: [{ id: "osint", label: "Live OSINT", icon: "globe" }, { id: "accounts", label: "Accounts", icon: "users" }, { id: "network", label: "Network & behavior", icon: "graph" }, { id: "graph", label: "Evidence graph", icon: "graph" }, { id: "entities", label: "Entity explorer", icon: "layers" }, { id: "media", label: "Media lab", icon: "media" }] },
  { label: "Evidence", items: [{ id: "comments", label: "Comments", icon: "narrative" }, { id: "findings", label: "Findings & review", icon: "check" }, { id: "compare", label: "Compare accounts", icon: "users" }, { id: "exports", label: "Exports", icon: "download" }] },
  { label: "System", items: [{ id: "connectors", label: "Connectors", icon: "link" }, { id: "agent", label: "Bounded agent", icon: "shield" }] },
];

function initialTab(goal: string): Tab {
  if (goal === "osint") return "osint";
  if (["media", "image_source"].includes(goal)) return "media";
  if (goal === "check_post") return "narratives";
  if (goal === "photo_location") return "geo";
  return "overview";
}

function readDeepLink(goal: string): { tab: Tab; focus: Focus } {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("tab") as Tab;
  const tab = TAB_IDS.includes(requested) ? requested : initialTab(goal);
  const focus: Focus = {};
  FOCUS_KEYS.forEach((key) => { const value = params.get(key); if (value) focus[key] = value; });
  return { tab, focus };
}

export default function Workspace({ caseId, initialGoal }: { caseId: string; initialGoal: string }) {
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [], truncated: false, total_nodes: 0, total_edges: 0 });
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [tab, setTab] = useState<Tab>(() => readDeepLink(initialGoal).tab);
  const [focus, setFocus] = useState<Focus>(() => readDeepLink(initialGoal).focus);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [refreshToken, setRefreshToken] = useState(0);
  const [relationFilter, setRelationFilter] = useState<string[]>([]);
  const [showCollector, setShowCollector] = useState(false);
  const [showJobs, setShowJobs] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analyticsError, setAnalyticsError] = useState("");

  const writeDeepLink = useCallback((nextTab: Tab, nextFocus: Focus, replace = false) => {
    const url = new URL(window.location.href);
    url.searchParams.set("case", caseId);
    url.searchParams.set("tab", nextTab);
    FOCUS_KEYS.forEach((key) => {
      const value = nextFocus[key];
      if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
    });
    window.history[replace ? "replaceState" : "pushState"]({ caseId, tab: nextTab, focus: nextFocus }, "", url);
  }, [caseId]);

  const navigate = useCallback((next: string, nextFocus: Focus = {}) => {
    const nextTab = (TAB_IDS.includes(next as Tab) ? next : "overview") as Tab;
    setTab(nextTab); setFocus(nextFocus); setSelectedNode(null); setSelectedEdge(null);
    writeDeepLink(nextTab, nextFocus);
  }, [writeDeepLink]);

  useEffect(() => { writeDeepLink(tab, focus, true); }, []);
  useEffect(() => {
    const restore = () => {
      const next = readDeepLink(initialGoal);
      setTab(next.tab); setFocus(next.focus); setSelectedNode(null); setSelectedEdge(null);
    };
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, [initialGoal]);

  const refresh = useCallback(async () => {
    const results = await Promise.allSettled([
      api.getCase(caseId), api.graph(caseId, relationFilter.length ? relationFilter : undefined),
      api.jobs(caseId), api.analytics(caseId),
    ]);
    const [caseResult, graphResult, jobsResult, analyticsResult] = results;
    if (caseResult.status === "fulfilled") { setCaseData(caseResult.value); setError(""); }
    else setError(caseResult.reason instanceof ApiError ? caseResult.reason.message : String(caseResult.reason));
    if (graphResult.status === "fulfilled") setGraph(graphResult.value);
    if (jobsResult.status === "fulfilled") setJobs(jobsResult.value);
    if (analyticsResult.status === "fulfilled") { setAnalytics(analyticsResult.value); setAnalyticsError(""); }
    else setAnalyticsError(analyticsResult.reason instanceof ApiError ? analyticsResult.reason.message : String(analyticsResult.reason));
    setLoading(false);
  }, [caseId, relationFilter]);
  useEffect(() => { setLoading(true); refresh(); }, [refresh, refreshToken]);
  useEffect(() => {
    const active = jobs.some((job) => ["queued", "running"].includes(job.lifecycle));
    if (!active) return;
    setShowJobs(true);
    const timer = setInterval(refresh, 1800);
    return () => clearInterval(timer);
  }, [jobs, refresh]);
  useEffect(() => {
    if (tab !== "graph" || !focus.evidence) return;
    const node = graph.nodes.find((row) => row.entity_type === "evidence" && row.entity_id === focus.evidence);
    if (node) { setSelectedNode(node); setSelectedEdge(null); }
  }, [tab, focus.evidence, graph]);

  const bump = () => setRefreshToken((value) => value + 1);
  const activeJobs = jobs.filter((job) => ["queued", "running"].includes(job.lifecycle)).length;
  const unresolvedAlerts = analytics?.alerts.filter((alert) => alert.active && !["resolved", "dismissed"].includes(alert.status)) || [];

  return <div className="workspace">
    <header className="casebar">
      <div className="casebar-title"><span className="case-icon"><Icon name="layers" /></span><div><span className="eyebrow">ACTIVE INVESTIGATION</span><h1>{caseData?.title || "Loading case…"}</h1></div><span className="role-badge">{caseData?.my_role || "…"}</span></div>
      <GlobalSearch caseId={caseId} onSelect={(target) => { const { tab: next, ...targetFocus } = target; navigate(next, targetFocus); }} />
      <div className="casebar-actions"><button className="btn btn-secondary" onClick={() => setShowCollector(!showCollector)}><Icon name="upload" /> Collect & run</button><button className={`btn btn-quiet ${activeJobs ? "has-active" : ""}`} onClick={() => setShowJobs(!showJobs)}><Icon name="clock" /> Jobs {activeJobs > 0 && <span className="count-badge">{activeJobs}</span>}</button></div>
    </header>
    {showCollector && <UploadBar caseId={caseId} caseData={caseData} initialGoal={initialGoal} onChanged={bump} onClose={() => setShowCollector(false)} />}
    {error && <div className="workspace-error"><Icon name="alert" />{error}<button onClick={refresh}>Retry</button></div>}
    <div className="workspace-body">
      <aside className="workspace-nav"><nav>{NAV_GROUPS.map((group) => <div className="nav-group" key={group.label}><span className="nav-label">{group.label}</span>{group.items.map((item) => <button key={item.id} aria-current={tab === item.id ? "page" : undefined} className={tab === item.id ? "active" : ""} onClick={() => navigate(item.id)}><Icon name={item.icon} size={17} /><span>{item.label}</span>{["overview", "alerts"].includes(item.id) && unresolvedAlerts.some((alert) => ["high", "elevated"].includes(alert.severity)) && <i className="nav-alert" />}</button>)}</div>)}</nav><div className="nav-evidence-legend"><span>EVIDENCE LANGUAGE</span><div><i className="fact" />Established</div><div><i className="signal" />Signal / similarity</div><div><i className="unknown" />Unknown / limited</div></div></aside>
      <main className="workspace-main">
        {loading && <div className="top-loading"><span className="spinner dark" /> Syncing case evidence…</div>}
        {tab === "overview" && <OverviewView data={analytics} loading={loading} error={analyticsError} onRefresh={bump} onNavigate={navigate} onCollect={() => setShowCollector(true)} />}
        {tab === "alerts" && <AlertsView caseId={caseId} role={caseData?.my_role || "viewer"} refreshToken={refreshToken} onChanged={bump} initialAlertId={focus.alert} />}
        {tab === "narratives" && <NarrativesView data={analytics} onRefresh={bump} initialPostId={focus.post} />}
        {tab === "network" && <NetworkView data={analytics} onRefresh={bump} onAccount={(accountId) => navigate("accounts", { account: accountId })} />}
        {tab === "accounts" && <AccountsView caseId={caseId} refreshToken={refreshToken} initialAccountId={focus.account} />}
        {tab === "geo" && <GeoView data={analytics} onRefresh={bump} />}
        {tab === "osint" && <OsintView caseId={caseId} role={caseData?.my_role || "viewer"} onChanged={bump} />}
        {tab === "media" && <MediaView caseId={caseId} role={caseData?.my_role || "viewer"} jobs={jobs} onChanged={bump} />}
        {tab === "graph" && <div className="graph-view-layout"><LeftPanel caseId={caseId} graph={graph} relationFilter={relationFilter} onFilterChange={(rels) => { setRelationFilter(rels); bump(); }} onRefresh={bump} /><div className="graph-center"><GraphCanvas data={graph} refreshToken={refreshToken} onSelectNode={(node) => { setSelectedNode(node); setSelectedEdge(null); }} onSelectEdge={(edge) => { setSelectedEdge(edge); setSelectedNode(null); }} /></div><EvidenceDrawer caseId={caseId} node={selectedNode} edge={selectedEdge} onClose={() => { setSelectedNode(null); setSelectedEdge(null); }} /></div>}
        {tab === "entities" && <EntityList graph={graph} onPick={(node) => {
          if (node.entity_type === "account") { navigate("accounts", { account: node.entity_id }); return; }
          const nextFocus = node.entity_type === "evidence" ? { evidence: node.entity_id } : node.entity_type === "post" ? { post: node.entity_id } : {};
          navigate(node.entity_type === "post" ? "narratives" : "graph", nextFocus);
          if (node.entity_type !== "post") setSelectedNode(node);
        }} />}
        {tab === "comments" && <CommentsView caseId={caseId} onChanged={bump} />}
        {tab === "findings" && <FindingsView caseId={caseId} role={caseData?.my_role || "viewer"} refreshToken={refreshToken} onChanged={bump} initialFindingId={focus.finding} />}
        {tab === "compare" && <CompareView caseId={caseId} graph={graph} />}
        {tab === "connectors" && <ConnectorsView caseId={caseId} role={caseData?.my_role || "viewer"} onChanged={bump} />}
        {tab === "exports" && <ExportsView caseId={caseId} role={caseData?.my_role || "viewer"} />}
        {tab === "agent" && <AgentView caseId={caseId} role={caseData?.my_role || "viewer"} />}
      </main>
    </div>
    {showJobs && <div className="jobs-drawer"><div className="jobs-drawer-head"><span>Background processing</span><button className="icon-button" aria-label="Close jobs" onClick={() => setShowJobs(false)}><Icon name="close" /></button></div><JobsPanel jobs={jobs} caseId={caseId} onChanged={refresh} /></div>}
  </div>;
}

function EntityList({ graph, onPick }: { graph: GraphData; onPick: (node: GraphNode) => void }) {
  const [query, setQuery] = useState("");
  const nodes = graph.nodes.filter((node) => `${node.label} ${node.entity_type}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="view-page"><div className="view-header"><div><span className="eyebrow">ENTITY EXPLORER</span><h1>Collected entities</h1><p>{graph.total_nodes} entities · {graph.total_edges} relationships {graph.truncated && "· truncated view"}</p></div></div><div className="search-field"><Icon name="search" /><input aria-label="Filter collected entities" placeholder="Filter by label or type…" value={query} onChange={(event) => setQuery(event.target.value)} /></div><div className="entity-grid">{nodes.map((node) => <button key={node.id} onClick={() => onPick(node)}><span className="mini-tag">{node.entity_type}</span><b>{node.label}</b><code>{node.entity_id}</code><Icon name="arrow" /></button>)}</div></div>;
}
