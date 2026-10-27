import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { AccountDetail, AccountSummary } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, ErrorView, MetricCard, PageHeader, ScopeNotice, ScoreMeter, formatDate } from "./AnalyticsPrimitives";

function safeUrl(value: string | null): string | null {
  if (!value) return null;
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.toString() : null; }
  catch { return null; }
}

export default function AccountsView({ caseId, refreshToken, initialAccountId }: {
  caseId: string; refreshToken: number; initialAccountId?: string;
}) {
  const [query, setQuery] = useState("");
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(initialAccountId || null);
  const [detail, setDetail] = useState<AccountDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (initialAccountId) setSelectedId(initialAccountId); }, [initialAccountId]);
  useEffect(() => {
    let current = true;
    const timer = window.setTimeout(async () => {
      setError("");
      try {
        const rows = await api.accounts(caseId, query.trim());
        if (current) setAccounts(rows);
      } catch (reason) { if (current) setError(reason instanceof ApiError ? reason.message : String(reason)); }
      finally { if (current) setLoading(false); }
    }, query ? 250 : 0);
    return () => { current = false; window.clearTimeout(timer); };
  }, [caseId, query, refreshToken]);
  useEffect(() => { if (!selectedId && accounts.length) setSelectedId(accounts[0].id); }, [accounts, selectedId]);

  const loadDetail = useCallback(async () => {
    if (!selectedId) { setDetail(null); return; }
    setDetailLoading(true); setError("");
    try { setDetail(await api.accountDetail(caseId, selectedId)); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : String(reason)); setDetail(null); }
    finally { setDetailLoading(false); }
  }, [caseId, selectedId]);
  useEffect(() => { loadDetail(); }, [loadDetail, refreshToken]);

  return <div className="view-page">
    <PageHeader eyebrow="ACCOUNT EVIDENCE" title="Accounts & observed behavior" description="Public/source-supplied identity metadata, post provenance, exact shared URLs and bounded graph/behavior indicators." />
    <ScopeNotice><b>Account-level indicators are not verdicts.</b> No private profile access, exact-person tracking, common-control inference or bot/deepfake certainty is presented.</ScopeNotice>
    <div className="filter-bar"><div className="search-field"><Icon name="search" size={16} /><input aria-label="Filter collected accounts" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter handle, display name or platform…" /></div><span className="small-muted">{accounts.length} accounts</span></div>
    {error && <ErrorView message={error} retry={loadDetail} />}
    {loading && !accounts.length ? <div className="view-loading"><span className="spinner dark" /><p>Loading account inventory…</p></div> : !accounts.length && !selectedId ? <EmptyView icon="users" title="No collected accounts" text="Import an authorized account/post bundle or collect a public Mastodon timeline. Account details are never synthesized." /> : <div className="accounts-layout">
      <div className="account-inventory">{accounts.map((account) => <button key={account.id} className={selectedId === account.id ? "active" : ""} onClick={() => setSelectedId(account.id)}>
        <span className="account-avatar">{account.handle.slice(0, 1).toUpperCase()}</span><span><b>@{account.handle}</b><small>{account.platform} · {account.post_count} posts</small><small>Collected {formatDate(account.last_collected_at)}</small></span><Icon name="chevron" size={15} />
      </button>)}</div>
      <div className="account-detail-wrap">{detailLoading && !detail ? <div className="view-loading"><span className="spinner dark" /><p>Correlating account evidence…</p></div> : detail ? <AccountEvidence detail={detail} /> : <EmptyView icon="users" title="Select an account" text="Choose a collected account to inspect evidence and limitations." />}</div>
    </div>}
  </div>;
}

function AccountEvidence({ detail }: { detail: AccountDetail }) {
  const { account, summary, behavior, network } = detail;
  const profile = safeUrl(account.canonical_profile_url);
  return <div className="account-evidence">
    <section className="card account-profile-card"><div className="detail-title"><div><span className="eyebrow">{account.platform} · CASE CORPUS IDENTITY</span><h2>@{account.handle}</h2><p>{account.display_name || "No source-supplied display name"}</p></div><span className={`status-badge ${account.identity_confirmed ? "available" : "insufficient"}`}>{account.identity_confirmed ? "identity confirmed by source" : "identity not independently confirmed"}</span></div>
      <div className="profile-links">{profile ? <a href={profile} target="_blank" rel="noreferrer">Open public profile <Icon name="external" size={13} /></a> : <span className="muted">No valid public profile URL</span>}<code>{account.id}</code></div>
    </section>
    <div className="metric-grid four"><MetricCard label="Collected posts" value={summary.post_count} note={`${summary.timestamped_post_count} source-timestamped`} icon="narrative" /><MetricCard label="Shared source URLs" value={summary.shared_url_count} note="Exact URL matches across accounts" icon="link" /><MetricCard label="Observed link degree" value={network?.observed_link_degree ?? 0} note={`${network?.fact_link_degree ?? 0} fact · ${network?.hypothesis_link_degree ?? 0} hypothesis`} icon="graph" /><MetricCard label="Bridge candidate" value={network?.bridge_candidate ? "Yes" : "No"} note={(network?.bridge_evidence_classes || []).join(" / ") || "No articulation point observed"} icon="users" tone={network?.bridge_candidate ? "warning" : "default"} /></div>
    <section className="card"><div className="card-head"><div><span className="eyebrow">PROVENANCE & COVERAGE</span><h2>Observation chronology</h2></div></div><div className="provenance-grid"><div><span>First source timestamp</span><b>{formatDate(summary.first_source_timestamp)}</b></div><div><span>Last source timestamp</span><b>{formatDate(summary.last_source_timestamp)}</b></div><div><span>First seen by Scamurai</span><b>{formatDate(summary.first_seen_at)}</b></div><div><span>Last collection contact</span><b>{formatDate(summary.last_collected_at)}</b></div></div><div className="coverage-chip-row"><span>Languages {Object.entries(summary.language_counts).map(([key, value]) => `${key}:${value}`).join(" · ") || "none"}</span><span>Domains {Object.entries(summary.domain_counts).map(([key, value]) => `${key}:${value}`).join(" · ") || "none"}</span></div></section>
    <div className="two-column-detail">
      <section className="card"><div className="card-head"><div><span className="eyebrow">BEHAVIOR SCREENING</span><h2>Automation indicators</h2></div></div>{behavior ? <><ScoreMeter score={behavior.automation_indicator_score} coverage={behavior.evidence_coverage} /><div className="feature-tags">{behavior.triggered_indicators.map((item) => <span key={item}>{item.replaceAll("_", " ")}</span>)}</div><details className="methodology-note"><summary><Icon name="info" /> Formula and limitations</summary><code>{behavior.formula}</code><pre>{JSON.stringify(behavior.features, null, 2)}</pre><ul>{behavior.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details></> : <EmptyView title="No behavior result" text="Not enough account-linked post data." />}</section>
      <section className="card"><div className="card-head"><div><span className="eyebrow">OBSERVED GRAPH POSITION</span><h2>Structural metrics</h2></div></div><div className="metric-pairs"><div><span>Fact PageRank</span><b>{network?.fact_pagerank ?? "—"}</b></div><div><span>Fact betweenness</span><b>{network?.fact_betweenness ?? "—"}</b></div><div><span>Hypothesis PageRank</span><b>{network?.hypothesis_pagerank ?? "—"}</b></div><div><span>Hypothesis betweenness</span><b>{network?.hypothesis_betweenness ?? "—"}</b></div></div><ScopeNotice>Structural position within this case graph only; not audience influence or account control.</ScopeNotice></section>
    </div>
    <section className="card"><div className="card-head"><div><span className="eyebrow">EXACT SHARED URLS</span><h2>Cross-account source overlap</h2></div><span className="small-muted">{detail.shared_urls.length} shown</span></div>{detail.shared_urls.length ? <div className="shared-url-list">{detail.shared_urls.map((row) => { const url = safeUrl(row.url); return <div key={row.url}><Icon name="link" /><span>{url ? <a href={url} target="_blank" rel="noreferrer">{row.url}</a> : <code>{row.url}</code>}<small>Also observed from {row.other_handles.map((handle) => `@${handle}`).join(", ")} · {row.note}</small></span></div>; })}</div> : <div className="empty-inline"><Icon name="info" />No exact URL shared with another collected account.</div>}</section>
    {detail.coordination_candidates.length > 0 && <section className="card"><div className="card-head"><div><span className="eyebrow">REVIEW HYPOTHESES</span><h2>Coordination candidates & alternatives</h2></div></div>{detail.coordination_candidates.map((candidate) => <details className="candidate-detail" key={candidate.id}><summary><span className="status-badge review_recommended">{candidate.review_state.replaceAll("_", " ")}</span><code>{candidate.id.slice(0, 12)}</code><span>{formatDate(candidate.created_at)}</span></summary><pre>{JSON.stringify(candidate.features, null, 2)}</pre><p><b>Baseline:</b> {candidate.baseline}</p><ul>{candidate.alternatives.map((item, index) => <li key={index}>{item}</li>)}</ul></details>)}</section>}
    <section className="card"><div className="card-head"><div><span className="eyebrow">SOURCE POSTS</span><h2>Post-level evidence & provenance</h2></div><span className="small-muted">{detail.coverage.posts_returned} / {detail.coverage.posts_total}</span></div><div className="table-wrap"><table className="data-table post-evidence-table"><thead><tr><th>Post</th><th>Source timestamp</th><th>First seen</th><th>Collected</th><th>Status</th></tr></thead><tbody>{detail.posts.map((post) => { const url = safeUrl(post.url); return <tr key={post.id}><td><b>{post.source_id || post.id.slice(0, 12)}</b><p>{post.text || "No text"}</p>{url && <a href={url} target="_blank" rel="noreferrer">Source <Icon name="external" size={12} /></a>}</td><td>{formatDate(post.source_timestamp)}<small>{post.timestamp_precision} precision</small></td><td>{formatDate(post.first_seen_at)}</td><td>{formatDate(post.collected_at)}</td><td><span className="mini-tag">{post.collection_status.replaceAll("_", " ")}</span><small>{post.language}</small></td></tr>; })}</tbody></table></div>{detail.coverage.truncated && <ScopeNotice tone="warning">Only the latest 200 account posts are displayed; the full case corpus remains subject to the analysis cap of {detail.coverage.analysis_post_cap}.</ScopeNotice>}</section>
    <details className="methodology-note"><summary><Icon name="info" /> Account interpretation boundaries</summary><ul>{detail.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
  </div>;
}
