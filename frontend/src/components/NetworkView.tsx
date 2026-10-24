import { useMemo, useState } from "react";
import type { AnalyticsData } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, MetricCard, PageHeader, ScopeNotice, ScoreMeter } from "./AnalyticsPrimitives";

export default function NetworkView({ data, onRefresh }: { data: AnalyticsData | null; onRefresh: () => void }) {
  const [showOnlyReview, setShowOnlyReview] = useState(false);
  const accounts = (data?.automation || []).filter((a) => !showOnlyReview || a.status === "review_recommended");
  const reviewCount = data?.automation.filter((a) => a.status === "review_recommended").length || 0;
  if (!data || !data.coverage.accounts) return <div className="view-page"><PageHeader eyebrow="ACCOUNT INTELLIGENCE" title="Network & behavior" description="Observed links and transparent account-level indicators." /><EmptyView icon="users" title="No account-linked data" text="Import posts with account handles to compute network and behavior features." /></div>;
  return <div className="view-page">
    <PageHeader eyebrow="ACCOUNT INTELLIGENCE" title="Network & behavior" description="Separate source-attributed links, coordination hypotheses and uncalibrated automation indicators." actions={<button className="btn btn-secondary" onClick={onRefresh}><Icon name="refresh" /> Recompute</button>} />
    <ScopeNotice><b>No bot probability or common-ownership verdict is produced.</b> Scheduling tools, newsrooms and genuine viral activity can create identical timing and repetition features.</ScopeNotice>
    <div className="metric-grid four"><MetricCard label="Observed accounts" value={data.network.nodes.length} note="Linked to collected posts" icon="users" /><MetricCard label="Fact links" value={data.network.edges.filter((e) => e.derivation_class === "fact").length} note="Public cross-links only" icon="link" /><MetricCard label="Hypothesis links" value={data.network.edges.filter((e) => e.derivation_class !== "fact").length} note="Require reviewer inspection" icon="graph" /><MetricCard label="Behavior review" value={reviewCount} note="Score + coverage thresholds" icon="alert" tone={reviewCount ? "warning" : "default"} /></div>
    <div className="network-grid">
      <section className="card span-two"><div className="card-head"><div><span className="eyebrow">ACCOUNT LINKAGE</span><h2>Observed relationship graph</h2></div><div className="graph-legend"><span className="fact-line">Fact</span><span className="hypothesis-line">Hypothesis</span></div></div><AccountGraph data={data} /></section>
      <section className="card"><div className="card-head"><div><span className="eyebrow">COMPONENTS</span><h2>Connected clusters</h2></div></div>{data.network.clusters.length ? <div className="cluster-list">{data.network.clusters.map((cluster, index) => <div className="cluster-card" key={cluster.account_ids.join("-")}><div><span className="cluster-index">C{index + 1}</span><b>{cluster.size} accounts</b></div><p>{cluster.handles.map((h) => `@${h}`).join(" · ")}</p><div className="case-meta"><span>{cluster.fact_links} fact</span><span>{cluster.hypothesis_links} hypothesis</span></div><small>{cluster.note}</small></div>)}</div> : <div className="empty-inline"><Icon name="info" /><span>No multi-account link components in the current graph.</span></div>}</section>
    </div>
    <section className="card"><div className="card-head"><div><span className="eyebrow">BEHAVIOR SCREENING</span><h2>Automation indicators</h2><p>Transparent weighted features; scores are not calibrated probabilities.</p></div><label className="toggle-label"><input type="checkbox" checked={showOnlyReview} onChange={(e) => setShowOnlyReview(e.target.checked)} /> Review only</label></div>
      <div className="table-wrap"><table className="data-table behavior-table"><thead><tr><th>Account</th><th>Observed posts</th><th>Heuristic score & coverage</th><th>Triggered features</th><th>Status</th></tr></thead><tbody>{accounts.map((account) => <tr key={account.account_id}><td><b>@{account.handle}</b><small>{account.platform}</small></td><td>{account.post_count}</td><td><ScoreMeter score={account.automation_indicator_score} coverage={account.evidence_coverage} /></td><td>{account.triggered_indicators.length ? <div className="feature-tags">{account.triggered_indicators.map((feature) => <span key={feature}>{feature.replaceAll("_", " ")}</span>)}</div> : <span className="muted">No threshold crossed</span>}</td><td><span className={`status-badge ${account.status}`}>{account.status.replaceAll("_", " ")}</span></td></tr>)}</tbody></table></div>
      <details className="methodology-note"><summary><Icon name="info" /> Score formula and feature values</summary>{accounts.map((account) => <div className="formula-row" key={account.account_id}><b>@{account.handle}</b><code>{account.formula}</code><pre>{JSON.stringify(account.features, null, 2)}</pre><ul>{account.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul></div>)}</details>
    </section>
  </div>;
}

function AccountGraph({ data }: { data: AnalyticsData }) {
  const layout = useMemo(() => {
    const nodes = data.network.nodes.slice(0, 12);
    const positions = new Map<string, { x: number; y: number }>();
    nodes.forEach((node, index) => {
      if (nodes.length === 1) positions.set(node.account_id, { x: 350, y: 170 });
      else {
        const angle = (Math.PI * 2 * index) / nodes.length - Math.PI / 2;
        positions.set(node.account_id, { x: 350 + Math.cos(angle) * 235, y: 170 + Math.sin(angle) * 120 });
      }
    });
    return { nodes, positions };
  }, [data]);
  if (!layout.nodes.length) return <div className="chart-empty">No account nodes</div>;
  return <div className="account-graph"><svg viewBox="0 0 700 340" role="img" aria-label="Observed account linkage graph">
    {data.network.edges.map((edge, index) => { const a = layout.positions.get(edge.source_account_id); const b = layout.positions.get(edge.target_account_id); if (!a || !b) return null; return <line key={index} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={edge.derivation_class === "fact" ? "edge-fact" : "edge-hypothesis"}><title>{edge.relationship}: {edge.statement}</title></line>; })}
    {layout.nodes.map((node) => { const pos = layout.positions.get(node.account_id)!; return <g key={node.account_id} transform={`translate(${pos.x},${pos.y})`} className="account-node"><circle r="24" /><text className="node-initial" textAnchor="middle" y="5">{node.handle.slice(0, 1).toUpperCase()}</text><text className="node-label" textAnchor="middle" y="43">@{node.handle.slice(0, 18)}</text><text className="node-subtitle" textAnchor="middle" y="58">{node.fact_link_degree} fact · {node.hypothesis_link_degree} hypothesis</text><title>{node.scope}</title></g>; })}
  </svg></div>;
}
