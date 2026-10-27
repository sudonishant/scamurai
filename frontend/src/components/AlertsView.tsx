import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { AlertItem } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, ErrorView, MetricCard, PageHeader, ScopeNotice, SeverityBadge, formatDate } from "./AnalyticsPrimitives";

const STATUSES = ["open", "acknowledged", "resolved", "dismissed"];

export default function AlertsView({ caseId, role, refreshToken, onChanged, initialAlertId }: {
  caseId: string; role: string; refreshToken: number; onChanged: () => void; initialAlertId?: string;
}) {
  const [rows, setRows] = useState<AlertItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(initialAlertId || null);
  const [activeFilter, setActiveFilter] = useState(initialAlertId ? "all" : "active");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewStatus, setReviewStatus] = useState("acknowledged");
  const [note, setNote] = useState("");
  const canReview = ["owner", "reviewer", "analyst"].includes(role);

  const load = useCallback(async () => {
    setError("");
    try { setRows(await api.alerts(caseId)); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : String(reason)); }
    finally { setLoading(false); }
  }, [caseId]);

  useEffect(() => { setLoading(true); load(); }, [load, refreshToken]);
  useEffect(() => { if (initialAlertId) { setSelectedId(initialAlertId); setActiveFilter("all"); } }, [initialAlertId]);
  const filtered = useMemo(() => rows.filter((row) =>
    (activeFilter === "all" || (activeFilter === "active") === row.active) &&
    (statusFilter === "all" || row.status === statusFilter)), [rows, activeFilter, statusFilter]);
  useEffect(() => {
    // Preserve a deep-linked ID while the first request is still in flight.
    if (loading && !rows.length) return;
    if (!filtered.some((row) => row.id === selectedId)) setSelectedId(filtered[0]?.id || null);
  }, [filtered, selectedId, loading, rows.length]);
  const selected = rows.find((row) => row.id === selectedId) || null;
  useEffect(() => {
    setNote(selected?.review_note || "");
    setReviewStatus(selected?.status === "open" ? "acknowledged" : selected?.status || "acknowledged");
  }, [selected?.id]);

  async function review() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      const updated = await api.reviewAlert(caseId, selected.id, reviewStatus, note);
      setRows((current) => current.map((row) => row.id === updated.id ? updated : row));
      onChanged();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  const unresolved = rows.filter((row) => row.active && !["resolved", "dismissed"].includes(row.status));
  const high = unresolved.filter((row) => ["high", "elevated"].includes(row.severity));
  return <div className="view-page">
    <PageHeader eyebrow="PERSISTENT REVIEW QUEUE" title="Alerts & analyst decisions" description="Materialized rule cues with durable acknowledgement, resolution, dismissal and audit history." actions={<button className="btn btn-secondary" onClick={load}><Icon name="refresh" /> Reload queue</button>} />
    <ScopeNotice><b>Alerts are review cues, not accusations.</b> Attention ranks triage; evidence completeness describes visible support only. Neither is a probability of coordination, maliciousness or truth.</ScopeNotice>
    <div className="metric-grid four">
      <MetricCard label="Active unresolved" value={unresolved.length} note={`${rows.length} persistent cues total`} icon="activity" />
      <MetricCard label="High / elevated" value={high.length} note="Requires evidence inspection" icon="alert" tone={high.length ? "warning" : "default"} />
      <MetricCard label="Acknowledged" value={rows.filter((row) => row.status === "acknowledged").length} note="Analyst review started" icon="check" />
      <MetricCard label="Inactive history" value={rows.filter((row) => !row.active).length} note="No longer rule-triggered" icon="clock" />
    </div>
    {error && <ErrorView message={error} retry={load} />}
    <div className="filter-bar">
      <div className="segmented-control" aria-label="Alert activity filter">{["active", "all", "inactive"].map((value) => <button key={value} className={activeFilter === value ? "active" : ""} onClick={() => setActiveFilter(value)}>{value}</button>)}</div>
      <select aria-label="Filter alerts by review status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All review states</option>{STATUSES.map((value) => <option key={value} value={value}>{value}</option>)}</select>
      <span className="small-muted">{filtered.length} shown</span>
    </div>
    {loading && !rows.length ? <div className="view-loading"><span className="spinner dark" /><p>Loading persistent alert queue…</p></div> : !filtered.length ? <EmptyView icon="check" title="No alerts in this filter" text="No rule cue matches the current activity/review filters. This does not establish absence of coordination." action={activeFilter !== "all" ? <button className="btn btn-secondary" onClick={() => setActiveFilter("all")}>Show all history</button> : undefined} /> : <div className="review-queue-layout">
      <div className="review-queue-list">{filtered.map((alert) => <button key={alert.id} className={`review-queue-item ${selectedId === alert.id ? "active" : ""}`} onClick={() => setSelectedId(alert.id)}>
        <div><SeverityBadge value={alert.severity} /><span className={`review-status ${alert.status}`}>{alert.status.replaceAll("_", " ")}</span>{!alert.active && <span className="mini-tag">INACTIVE</span>}</div>
        <b>{alert.title}</b><p>{alert.rule}</p><small>Last seen {formatDate(alert.last_seen_at)}</small>
      </button>)}</div>
      {selected && <section className="review-detail card" data-alert-id={selected.id}>
        <div className="detail-title"><div><span className="eyebrow">{selected.type.replaceAll("_", " ")}</span><h2>{selected.title}</h2></div><SeverityBadge value={selected.severity} /></div>
        <div className="detail-metrics three"><div><strong>{selected.attention_score ?? "—"}</strong><span>attention · uncalibrated</span></div><div><strong>{selected.evidence_confidence?.score ?? "—"}</strong><span>evidence completeness</span></div><div><strong>{selected.evidence_ids.length}</strong><span>linked references</span></div></div>
        <div className="alert-rule-block"><span className="mini-tag">TRIGGER RULE</span><code>{selected.rule}</code><p>{selected.recommended_action}</p></div>
        {selected.evidence_confidence?.formula && <details className="methodology-note" open><summary><Icon name="info" /> Evidence-completeness method</summary><code>{selected.evidence_confidence.formula}</code><pre>{JSON.stringify(selected.evidence_confidence.factors, null, 2)}</pre><ul>{selected.evidence_confidence.limitations?.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
        <div className="provenance-grid"><div><span>First materialized</span><b>{formatDate(selected.first_seen_at)}</b></div><div><span>Last rule match</span><b>{formatDate(selected.last_seen_at)}</b></div><div><span>Reviewed</span><b>{formatDate(selected.reviewed_at)}</b></div></div>
        {selected.limitations.length > 0 && <div className="assessment-box"><span className="mini-tag">ALTERNATIVES & LIMITS</span><ul>{selected.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
        <div className="evidence-id-list"><span className="mini-tag">EVIDENCE / ENTITY REFERENCES</span><div>{selected.evidence_ids.length ? selected.evidence_ids.slice(0, 30).map((id) => <code key={id}>{id}</code>) : <span className="muted">No supporting entity references; this may be a data-coverage cue.</span>}</div></div>
        {canReview ? <div className="review-action-panel">
          <div className="field"><label htmlFor="alert-review-status">Review state</label><select id="alert-review-status" value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}>{STATUSES.map((value) => <option key={value}>{value}</option>)}</select></div>
          <div className="field"><label htmlFor="alert-review-note">Analyst note · optional, max 4000 characters</label><textarea id="alert-review-note" rows={3} maxLength={4000} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Evidence checked, alternative explanations, next step…" /></div>
          <button className="btn btn-primary" disabled={busy} onClick={review}>{busy ? <span className="spinner" /> : <Icon name="check" />} Save audited review</button>
        </div> : <ScopeNotice>Your {role} role has read-only alert access. A reviewer, analyst or owner must record a decision.</ScopeNotice>}
      </section>}
    </div>}
  </div>;
}
