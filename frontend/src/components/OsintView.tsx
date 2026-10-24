import { useCallback, useEffect, useState } from "react";
import { api, ApiError, downloadOsintReport } from "../lib/api";
import type { OsintModule, OsintReport, OsintReportSummary } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, ErrorView, PageHeader, ScopeNotice, formatDate } from "./AnalyticsPrimitives";

const MODULE_INFO = [
  { id: "dns", name: "DNS & email policy", desc: "A, AAAA, MX, NS, TXT, CAA, DMARC" },
  { id: "rdap", name: "Registration data", desc: "Authoritative RDAP via IANA bootstrap" },
  { id: "web", name: "Public web metadata", desc: "One bounded page, headers and redirects" },
  { id: "certificates", name: "Certificate Transparency", desc: "Historical crt.sh hostname observations" },
  { id: "archive", name: "Wayback availability", desc: "One closest accessible archive snapshot" },
];

type Section = "overview" | "dns" | "rdap" | "web" | "certificates" | "archive" | "raw";

export default function OsintView({ caseId, role, onChanged }: { caseId: string; role: string; onChanged: () => void }) {
  const [target, setTarget] = useState("");
  const [selectedModules, setSelectedModules] = useState(MODULE_INFO.map((m) => m.id));
  const [reports, setReports] = useState<OsintReportSummary[]>([]);
  const [report, setReport] = useState<OsintReport | null>(null);
  const [section, setSection] = useState<Section>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const canRun = ["owner", "analyst"].includes(role);

  const loadReports = useCallback(async () => {
    try { setReports(await api.osintReports(caseId)); }
    catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
  }, [caseId]);
  useEffect(() => { setReport(null); loadReports(); }, [loadReports]);

  async function investigate() {
    if (!target.trim()) return;
    setBusy(true); setError("");
    try {
      const result = await api.investigateOsint(caseId, target.trim(), selectedModules);
      setReport(result); setSection("overview"); await loadReports(); onChanged();
    } catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function openReport(id: string) {
    setError("");
    try { setReport(await api.osintReport(caseId, id)); setSection("overview"); }
    catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
  }

  const module = (name: string) => report?.modules.find((m) => m.module === name) || null;
  return <div className="view-page">
    <PageHeader eyebrow="LIVE PUBLIC INFRASTRUCTURE" title="Live OSINT workbench" description="Real bounded requests with source-attributed DNS, registration, web, certificate and archive observations. No demo results." actions={report?.id && <button className="btn btn-secondary" onClick={() => downloadOsintReport(caseId, report.id!)}><Icon name="download" /> Export evidence JSON</button>} />
    <ScopeNotice><b>Research, not intrusion.</b> No port scanning, exploit, breach lookup, login bypass or private identity resolution. Public observations are time-sensitive and require corroboration.</ScopeNotice>
    <section className="card osint-search-card">
      <div className="osint-target-row"><div className="search-field large"><Icon name="globe" /><input value={target} onChange={(e) => setTarget(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !busy) investigate(); }} placeholder="example.com or https://example.com/public-page" disabled={!canRun || busy} /></div><button className="btn btn-primary" disabled={!canRun || busy || !target.trim() || !selectedModules.length} onClick={investigate}>{busy ? <span className="spinner" /> : <Icon name="search" />}{busy ? "Collecting sources…" : "Investigate target"}</button></div>
      <div className="module-picker">{MODULE_INFO.map((item) => <label key={item.id} className={selectedModules.includes(item.id) ? "selected" : ""}><input type="checkbox" checked={selectedModules.includes(item.id)} disabled={!canRun || busy} onChange={() => setSelectedModules((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id])} /><span><b>{item.name}</b><small>{item.desc}</small></span></label>)}</div>
      {!canRun && <p className="limitation">Your {role} role is read-only; existing reports remain available.</p>}
    </section>
    {busy && <div className="collection-progress"><span className="spinner dark" /><div><b>Querying independent public sources</b><p>Slow CT/registry responses do not block other modules. No browser-side fallback values are generated.</p></div></div>}
    {error && <ErrorView message={error} retry={loadReports} />}
    <div className="osint-layout">
      <aside className="report-history"><div className="card-head"><h3>Report history</h3><button className="icon-button" aria-label="Refresh report history" onClick={loadReports}><Icon name="refresh" size={15} /></button></div>{reports.length ? reports.map((item) => <button key={item.id} className={report?.id === item.id ? "active" : ""} onClick={() => openReport(item.id)}><div><b>{item.target}</b><StatusBadge status={item.status} /></div><span>{formatDate(item.created_at)}</span><small>{item.summary.sources_succeeded}/{item.summary.sources_total} sources returned</small></button>) : <p className="muted">No saved reports. Run a bounded investigation to create one.</p>}</aside>
      <main className="osint-result">{!report ? <EmptyView icon="globe" title="No report selected" text="Enter a public domain or URL, or open a previous source-attributed report." /> : <>
        <div className="report-heading"><div><span className="eyebrow">{report.schema_version}</span><h2>{report.normalized_target}</h2><p>Generated {formatDate(report.generated_at)} · {report.target_type}</p></div><StatusBadge status={report.status} /></div>
        <div className="report-summary"><div><strong>{report.summary.sources_succeeded}</strong><span>sources returned</span></div><div><strong>{report.summary.sources_limited}</strong><span>limited / failed</span></div><div><strong>{report.modules.length}</strong><span>independent modules</span></div>{report.object_hash && <div className="hash-summary"><span>SHA-256 evidence manifest</span><code>{report.object_hash}</code></div>}</div>
        <nav className="subtabs">{(["overview", ...report.modules.map((m) => m.module), "raw"] as Section[]).map((item) => <button key={item} className={section === item ? "active" : ""} onClick={() => setSection(item)}>{item === "certificates" ? "Certificates" : item[0].toUpperCase() + item.slice(1)}</button>)}</nav>
        {section === "overview" && <Overview report={report} onOpen={(name) => setSection(name as Section)} />}
        {section === "raw" && <pre className="raw-json">{JSON.stringify(report, null, 2)}</pre>}
        {section !== "overview" && section !== "raw" && <ModuleDetail module={module(section)} />}
      </>}</main>
    </div>
    {report && <details className="methodology-note"><summary><Icon name="info" /> Report limitations</summary><ul>{report.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
  </div>;
}

function StatusBadge({ status }: { status: string }) {
  const good = ["successful", "complete", "configured"].includes(status);
  const empty = status === "successful_empty";
  return <span className={`source-status ${good ? "good" : empty ? "empty" : "limited"}`}><span />{status.replaceAll("_", " ")}</span>;
}

function Overview({ report, onOpen }: { report: OsintReport; onOpen: (name: string) => void }) {
  return <div className="module-overview">{report.modules.map((module) => <button className="module-result-card" key={module.module} onClick={() => onOpen(module.module)}><div><span className="icon-tile"><Icon name={module.module === "dns" ? "layers" : module.module === "rdap" ? "file" : module.module === "web" ? "globe" : module.module === "archive" ? "clock" : "shield"} /></span><StatusBadge status={module.status} /></div><h3>{MODULE_INFO.find((m) => m.id === module.module)?.name || module.module}</h3><p>{module.error?.detail || moduleSummary(module)}</p><small>{formatDate(module.collected_at)}</small><span className="goal-action">Inspect evidence <Icon name="arrow" size={14} /></span></button>)}</div>;
}

function moduleSummary(module: OsintModule): string {
  const data = module.data || {};
  if (module.module === "dns") return `${Array.isArray(data.records) ? data.records.length : 0} DNS answers observed`;
  if (module.module === "rdap") return String(data.name || data.handle || "Registration record observed");
  if (module.module === "web") return String(data.title || data.final_url || "Web metadata observed");
  if (module.module === "certificates") return `${data.unique_hostname_count || 0} historical hostnames · ${data.certificate_record_count || 0} records`;
  if (module.module === "archive") return data.snapshot ? "Closest archive snapshot available" : "No closest snapshot returned";
  return "Source observation available";
}

function ModuleDetail({ module }: { module: OsintModule | null }) {
  if (!module) return <EmptyView title="Module not present" text="This source was not selected for the report." />;
  if (!module.data) return <div className="source-failure"><Icon name="alert" size={26} /><h3>{module.status.replaceAll("_", " ")}</h3><p>{module.error?.detail || "No source data returned."}</p><small>HTTP {module.error?.status_code ?? "—"} · This failure is not an empty result.</small></div>;
  const data = module.data;
  return <section className="module-detail">
    <div className="detail-title"><div><span className="eyebrow">SOURCE MODULE</span><h2>{MODULE_INFO.find((m) => m.id === module.module)?.name || module.module}</h2></div><StatusBadge status={module.status} /></div>
    {module.module === "dns" && <DnsData data={data} />}
    {module.module === "rdap" && <RdapData data={data} />}
    {module.module === "web" && <WebData data={data} />}
    {module.module === "certificates" && <CertificateData data={data} />}
    {module.module === "archive" && <ArchiveData data={data} />}
    {data.source && <SourceAttribution source={data.source} />}
    {Array.isArray(data.limitations) && <ScopeNotice><ul className="compact-list">{data.limitations.map((item: string, i: number) => <li key={i}>{item}</li>)}</ul></ScopeNotice>}
  </section>;
}

function DnsData({ data }: { data: Record<string, any> }) {
  return <><div className="table-wrap"><table className="data-table"><thead><tr><th>Name</th><th>Type</th><th>TTL</th><th>Observed value</th></tr></thead><tbody>{(data.records || []).map((row: any, i: number) => <tr key={i}><td>{row.name}</td><td><span className="mini-tag">{row.type}</span></td><td>{row.ttl}</td><td><code className="wrap-code">{row.data}</code></td></tr>)}</tbody></table></div>{!(data.records || []).length && <div className="empty-inline"><Icon name="info" />No DNS answers in the successful responses.</div>}{data.email_security && <div className="info-panels"><div><b>Email authentication declarations</b><p>MX observed: {String(data.email_security.mx_observed)}</p><p>SPF: {(data.email_security.spf_records_observed || []).join(" · ") || "Not observed"}</p><p>DMARC: {(data.email_security.dmarc_records_observed || []).join(" · ") || "Not observed"}</p><small>{data.email_security.note}</small></div><div><b>Resolver query health</b>{(data.queries || []).map((query: any, i: number) => <p key={i}>{query.query} / {query.type}: {query.rcode_label} · AD={String(query.authenticated_data)}</p>)}{(data.errors || []).map((error: any, i: number) => <p className="limitation" key={i}>{error.query}/{error.type}: {error.outcome}</p>)}</div></div>}</>;
}

function RdapData({ data }: { data: Record<string, any> }) {
  return <><div className="info-panels"><div><b>Registry object</b><p>Name: {data.name || "—"}</p><p>Handle: {data.handle || "—"}</p><p>Status: {(data.status || []).join(", ") || "—"}</p>{data.network && <p>Range: {data.network.startAddress || "—"} — {data.network.endAddress || "—"}</p>}</div><div><b>Registration events</b>{(data.events || []).map((event: any, i: number) => <p key={i}>{event.action}: {formatDate(event.date)}</p>)}{!(data.events || []).length && <p>No events supplied</p>}</div></div><div className="info-panels"><div><b>Nameservers</b>{(data.nameservers || []).map((name: string) => <p key={name}><code>{name}</code></p>)}</div><div><b>Operational entities</b>{(data.entities || []).map((entity: any, i: number) => <p key={i}>{entity.name || entity.handle || "Unnamed"} · {(entity.roles || []).join(", ")}</p>)}<small>Registrant personal contact fields are intentionally excluded.</small></div></div></>;
}

function WebData({ data }: { data: Record<string, any> }) {
  return <><div className="web-title-card"><span className="mini-tag">HTTP {String(data.http_status)}</span><h3>{data.title || "No HTML title observed"}</h3><p>{data.h1 || "No H1 observed"}</p><a href={data.final_url} target="_blank" rel="noreferrer">{data.final_url} <Icon name="external" size={13} /></a></div><div className="table-wrap"><table className="data-table"><thead><tr><th>Security header</th><th>Present</th><th>Self-reported value</th></tr></thead><tbody>{Object.entries(data.security_headers || {}).map(([name, row]: [string, any]) => <tr key={name}><td><code>{name}</code></td><td>{row.present ? <span className="text-success">Yes</span> : <span className="text-warning">Not observed</span>}</td><td>{row.value || "—"}</td></tr>)}</tbody></table></div>{(data.technologies_reported || []).length > 0 && <div className="feature-tags">{(data.technologies_reported || []).map((tech: any, i: number) => <span key={i}>{tech.name} · {tech.reported_by}</span>)}</div>}</>;
}

function CertificateData({ data }: { data: Record<string, any> }) {
  return <><div className="detail-metrics"><div><strong>{data.unique_hostname_count || 0}</strong><span>unique names</span></div><div><strong>{data.certificate_record_count || 0}</strong><span>certificate records</span></div><div><strong>{data.truncated ? "Yes" : "No"}</strong><span>result truncated</span></div></div><div className="hostname-grid">{(data.hostnames || []).map((name: string) => <code key={name}>{name}</code>)}</div><p className="muted">Log window observed: {data.first_log_timestamp_observed || "—"} → {data.last_log_timestamp_observed || "—"}</p></>;
}

function ArchiveData({ data }: { data: Record<string, any> }) {
  return data.snapshot ? <div className="web-title-card"><span className="mini-tag">CLOSEST SNAPSHOT</span><h3>{data.snapshot.timestamp}</h3><p>Available: {String(data.snapshot.available)} · HTTP {data.snapshot.status}</p>{data.snapshot.url && <a href={data.snapshot.url} target="_blank" rel="noreferrer">Open archived snapshot <Icon name="external" size={13} /></a>}</div> : <div className="empty-inline"><Icon name="clock" /><span>{data.note || "No closest snapshot returned."}</span></div>;
}

function SourceAttribution({ source }: { source: Record<string, any> }) {
  return <div className="source-attribution"><Icon name="link" /><div><b>{source.name}</b><code>{source.query_url}</code></div>{source.documentation && <a href={source.documentation} target="_blank" rel="noreferrer">Method docs <Icon name="external" size={12} /></a>}</div>;
}
