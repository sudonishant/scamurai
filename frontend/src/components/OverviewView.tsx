import type { AnalyticsData } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, ErrorView, MetricCard, PageHeader, ScopeNotice, SeverityBadge, TimelineBars, formatDate } from "./AnalyticsPrimitives";

export default function OverviewView({ data, loading, error, onRefresh, onNavigate, onCollect }: {
  data: AnalyticsData | null; loading: boolean; error: string; onRefresh: () => void;
  onNavigate: (tab: string, focus?: { alert?: string }) => void; onCollect: () => void;
}) {
  if (loading && !data) return <div className="view-loading"><span className="spinner dark" /><p>Computing corpus analytics…</p></div>;
  if (error && !data) return <ErrorView message={error} retry={onRefresh} />;
  if (!data) return <EmptyView title="No analytics yet" text="Collect public posts or import an authorized corpus, then refresh." action={<button className="btn btn-primary" onClick={onCollect}><Icon name="upload" /> Collect data</button>} />;
  const coverage = data.coverage;
  const activeNarratives = data.narratives.filter((n) => n.account_count > 1);
  const activeAlerts = data.alerts.filter((a) => a.active && !["resolved", "dismissed"].includes(a.status));
  const highAlerts = activeAlerts.filter((a) => ["high", "elevated"].includes(String(a.severity)));
  return <div className="view-page">
    <PageHeader eyebrow="MISSION OVERVIEW" title="Situation awareness" description={data.scope} actions={<><button className="btn btn-secondary" onClick={onRefresh}><Icon name="refresh" /> Refresh analytics</button><button className="btn btn-primary" onClick={onCollect}><Icon name="upload" /> Collect data</button></>} />
    {error && <ErrorView message={error} retry={onRefresh} />}
    <div className="metric-grid five">
      <MetricCard label="Collected posts" value={Number(coverage.posts || 0)} note={`${Number(coverage.timestamped_posts || 0)} timestamped`} icon="narrative" />
      <MetricCard label="Observed accounts" value={Number(coverage.accounts || 0)} note="Case-corpus identities" icon="users" />
      <MetricCard label="Narrative candidates" value={activeNarratives.length} note="Cross-account lexical clusters" icon="activity" />
      <MetricCard label="Review alerts" value={highAlerts.length} note={`${activeAlerts.length} active including data gaps`} icon="alert" tone={highAlerts.length ? "warning" : "default"} />
      <MetricCard label="Media assets" value={Number(coverage.media_assets || 0)} note="Available for forensics" icon="media" />
    </div>

    <div className="overview-grid">
      <section className="card span-two">
        <div className="card-head"><div><span className="eyebrow">PRIORITY QUEUE</span><h2>Early warnings & review cues</h2></div><span className="small-muted">Rule-based · not accusations</span></div>
        {activeAlerts.length === 0 ? <div className="empty-inline"><Icon name="check" /><span>No unresolved threshold cue in the current corpus. This does not establish absence of coordination.</span></div> : <div className="alert-list">{activeAlerts.slice(0, 6).map((alert) => <button className="alert-row" key={String(alert.id)} onClick={() => onNavigate("alerts", { alert: String(alert.id) })}>
          <SeverityBadge value={String(alert.severity)} />
          <div className="alert-copy"><b>{String(alert.title)}</b><p>{String(alert.rule)}</p><small>{String(alert.recommended_action || "Review evidence")}</small></div>
          {alert.attention_score !== null && alert.attention_score !== undefined && <span className="attention-score"><b>{String(alert.attention_score)}</b><small>attention</small></span>}
          <Icon name="chevron" size={16} />
        </button>)}</div>}
      </section>

      <section className="card coverage-card">
        <div className="card-head"><div><span className="eyebrow">DATA HEALTH</span><h2>Evidence coverage</h2></div><Icon name="database" /></div>
        <CoverageBar label="Timestamp coverage" value={Number(coverage.timestamp_coverage || 0)} />
        <CoverageBar label="Geolocated posts" value={Number(coverage.posts) ? Number(coverage.geolocated_posts || 0) / Number(coverage.posts) : 0} />
        <div className="coverage-facts"><div><span>Reference time</span><b>{formatDate(data.reference_time)}</b></div><div><span>Analysis refreshed</span><b>{formatDate(data.generated_at)}</b></div><div><span>Source access records</span><b>{String(coverage.source_access_records || 0)}</b></div></div>
        <ScopeNotice>Missing or inaccessible data is a coverage limitation—not evidence that a narrative, account or location does not exist.</ScopeNotice>
      </section>
    </div>

    <section className="card">
      <div className="card-head"><div><span className="eyebrow">NARRATIVE PULSE</span><h2>What is moving through the corpus</h2></div><button className="text-button" onClick={() => onNavigate("narratives")}>Explore all <Icon name="arrow" size={14} /></button></div>
      {data.narratives.length === 0 ? <EmptyView title="No narrative candidates" text="Import posts with text to build lexical clusters and timelines." /> : <div className="narrative-pulse-grid">{data.narratives.slice(0, 3).map((narrative) => <button className="pulse-card" key={narrative.id} onClick={() => onNavigate("narratives")}>
        <div className="pulse-head"><span className={`status-dot ${narrative.early_warning ? "hot" : ""}`} /><b>{narrative.label}</b><Icon name="arrow" size={15} /></div>
        <div className="pulse-meta"><span>{narrative.post_count} posts</span><span>{narrative.account_count} accounts</span><span>{narrative.bucket_size} buckets</span></div>
        <TimelineBars rows={narrative.timeline} height={95} />
        <div className="pulse-footer"><span>First observed {formatDate(narrative.first_observed)}</span>{narrative.early_warning && <SeverityBadge value={String(narrative.early_warning.severity)} />}</div>
      </button>)}</div>}
    </section>

    <section className="quick-grid">
      <button className="quick-card" onClick={() => onNavigate("osint")}><span className="icon-tile"><Icon name="globe" /></span><div><b>Investigate public infrastructure</b><p>Run source-attributed DNS, RDAP, CT and archive lookups.</p></div><Icon name="arrow" /></button>
      <button className="quick-card" onClick={() => onNavigate("media")}><span className="icon-tile"><Icon name="media" /></span><div><b>Open media lab</b><p>Inspect metadata and residuals; keep model output separate.</p></div><Icon name="arrow" /></button>
      <button className="quick-card" onClick={() => onNavigate("connectors")}><span className="icon-tile"><Icon name="link" /></span><div><b>Check collection access</b><p>Review provider state and import public Mastodon timelines.</p></div><Icon name="arrow" /></button>
    </section>
    <details className="methodology-note"><summary><Icon name="info" /> Interpretation boundaries</summary><ul>{data.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
  </div>;
}

function CoverageBar({ label, value }: { label: string; value: number }) {
  const bounded = Math.max(0, Math.min(1, value || 0));
  return <div className="coverage-bar"><div><span>{label}</span><b>{(bounded * 100).toFixed(0)}%</b></div><div className="meter-track"><div style={{ width: `${bounded * 100}%` }} /></div></div>;
}
