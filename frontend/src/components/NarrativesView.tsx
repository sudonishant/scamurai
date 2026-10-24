import { useEffect, useMemo, useState } from "react";
import type { AnalyticsData, Narrative } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, PageHeader, ScopeNotice, SeverityBadge, TimelineBars, formatDate } from "./AnalyticsPrimitives";

export default function NarrativesView({ data, onRefresh, initialPostId }: { data: AnalyticsData | null; onRefresh: () => void; initialPostId?: string }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [crossOnly, setCrossOnly] = useState(false);
  const narratives = useMemo(() => (data?.narratives || []).filter((n) => (!crossOnly || n.account_count > 1) && (!query || `${n.label} ${n.top_terms.map((t) => t.term).join(" ")}`.toLowerCase().includes(query.toLowerCase()))), [data, query, crossOnly]);
  useEffect(() => { if (!narratives.some((n) => n.id === selectedId)) setSelectedId(narratives[0]?.id || null); }, [narratives, selectedId]);
  useEffect(() => {
    if (!initialPostId || !data) return;
    const match = data.narratives.find((n) => n.evidence_post_ids.includes(initialPostId));
    if (match) {
      setSelectedId(match.id);
      window.setTimeout(() => document.getElementById(`narrative-post-${initialPostId}`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 80);
    }
  }, [initialPostId, data]);
  const selected = narratives.find((n) => n.id === selectedId) || null;
  const missingFocusedPost = Boolean(initialPostId && data && !data.narratives.some((n) => n.evidence_post_ids.includes(initialPostId)));
  return <div className="view-page">
    <PageHeader eyebrow="NARRATIVE INTELLIGENCE" title="Narratives & propagation" description="Lexical clusters, observed timing and amplification order inside the authorized corpus." actions={<button className="btn btn-secondary" onClick={onRefresh}><Icon name="refresh" /> Recompute</button>} />
    <ScopeNotice><b>“Earliest observed” is not “originator”.</b> Collection gaps, deleted posts and timestamp precision can change the order. Similarity alone cannot classify discourse as organic or orchestrated.</ScopeNotice>
    {missingFocusedPost && <ScopeNotice tone="warning">The linked post is outside the current lexical analysis cap or has no matching narrative candidate. Open the account evidence view for post-level provenance.</ScopeNotice>}
    <div className="filter-bar"><div className="search-field"><Icon name="search" size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter narratives or terms…" /></div><label className="toggle-label"><input type="checkbox" checked={crossOnly} onChange={(e) => setCrossOnly(e.target.checked)} /> Cross-account only</label><span className="small-muted">{narratives.length} candidates</span></div>
    {!data || data.coverage.posts === 0 ? <EmptyView title="No post corpus" text="Import an authorized posts JSON bundle or collect a public Mastodon hashtag timeline." /> : narratives.length === 0 ? <EmptyView icon="search" title="No matching narratives" text="Change the filter or inspect the collection coverage." /> : <div className="narrative-layout">
      <div className="narrative-list">{narratives.map((narrative) => <button key={narrative.id} className={`narrative-list-item ${selectedId === narrative.id ? "active" : ""}`} onClick={() => setSelectedId(narrative.id)}>
        <div className="narrative-item-top"><span className={`status-dot ${narrative.early_warning ? "hot" : ""}`} /><b>{narrative.label}</b>{narrative.early_warning && <SeverityBadge value={String(narrative.early_warning.severity)} />}</div>
        <p>{narrative.representative_posts[0]?.text || "No representative text"}</p>
        <div><span>{narrative.post_count} posts</span><span>{narrative.account_count} accounts</span><span>{formatDate(narrative.last_observed)}</span></div>
      </button>)}</div>
      {selected && <NarrativeDetail narrative={selected} focusPostId={initialPostId} />}
    </div>}
  </div>;
}

function NarrativeDetail({ narrative, focusPostId }: { narrative: Narrative; focusPostId?: string }) {
  return <section className="narrative-detail">
    <div className="detail-title"><div><span className="eyebrow">{narrative.id}</span><h2>{narrative.label}</h2></div>{narrative.early_warning && <SeverityBadge value={String(narrative.early_warning.severity)} />}</div>
    <div className="detail-metrics"><div><strong>{narrative.post_count}</strong><span>posts</span></div><div><strong>{narrative.account_count}</strong><span>accounts</span></div><div><strong>{narrative.timeline.length}</strong><span>{narrative.bucket_size} buckets</span></div><div><strong>{narrative.undated_posts}</strong><span>undated</span></div></div>
    <div className="card inner"><div className="card-head"><h3>Observed volume timeline</h3><span className="small-muted">Zero-filled between first and last observation</span></div><TimelineBars rows={narrative.timeline} height={150} /></div>
    {narrative.early_warning && <div className="warning-explainer"><Icon name="alert" /><div><b>Acceleration rule crossed · attention {String(narrative.early_warning.attention_score)}/100</b><p>{String(narrative.early_warning.rule)}</p><small>Latest {String(narrative.early_warning.latest_count)} · baseline [{Array.isArray(narrative.early_warning.baseline_counts) ? narrative.early_warning.baseline_counts.join(", ") : "—"}] · this is not campaign probability.</small></div></div>}
    <div className="two-column-detail">
      <div className="card inner"><div className="card-head"><h3>Earliest & amplification order</h3></div>
        {narrative.earliest_observed && <div className="origin-card"><span className="mini-tag">EARLIEST OBSERVED</span><b>@{narrative.earliest_observed.handle}</b><span>Source {formatDate(narrative.earliest_observed.observed_at)}</span><small>First seen by Scamurai {formatDate(narrative.earliest_observed.first_seen_at)}</small><small>{narrative.earliest_observed.scope}</small></div>}
        <div className="propagation-list">{narrative.propagation.map((row, index) => <div key={row.account_id}><span className="order-index">{index + 1}</span><span><b>@{row.handle}</b><small>{formatDate(row.first_observed)}</small></span><span className="mini-tag">{row.role === "earliest_observed" ? "FIRST" : "LATER"}</span></div>)}</div>
        {!narrative.propagation.length && <p className="muted">No account-linked propagation records.</p>}
      </div>
      <div className="card inner"><div className="card-head"><h3>Top lexical terms</h3></div><div className="term-cloud">{narrative.top_terms.map((term) => <span key={term.term}>{term.term}<b>{term.count}</b></span>)}</div><div className="assessment-box"><span className="mini-tag">INTERPRETATION</span><b>{narrative.discourse_assessment.state.replaceAll("_", " ")}</b><p>{narrative.discourse_assessment.interpretation}</p><small>{narrative.analysis_scope}</small></div></div>
    </div>
    <div className="card inner"><div className="card-head"><h3>Representative source posts</h3><span className="small-muted">{narrative.evidence_post_ids.length} linked evidence posts</span></div><div className="source-post-list">{narrative.representative_posts.map((post) => <article id={`narrative-post-${post.id}`} className={focusPostId === post.id ? "focused-evidence" : ""} key={post.id}><div><b>@{post.handle}</b><span>Source {formatDate(post.observed_at)} · {post.timestamp_precision} precision</span></div><p>{post.text}</p><div className="post-provenance"><span>First seen {formatDate(post.first_seen_at)}</span><span>Collected {formatDate(post.collected_at)}</span></div><footer><span className="mono">{post.id.slice(0, 12)}</span>{post.url && <a href={post.url} target="_blank" rel="noreferrer">Open source <Icon name="external" size={13} /></a>}</footer></article>)}</div></div>
  </section>;
}
