import type { ReactNode } from "react";
import Icon from "./Icon";

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="view-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="view-actions">{actions}</div>}</div>;
}

export function MetricCard({ label, value, note, icon, tone = "default" }: { label: string; value: ReactNode; note: string; icon: string; tone?: string }) {
  return <div className={`metric-card ${tone}`}><div className="metric-top"><span>{label}</span><Icon name={icon} /></div><strong>{value}</strong><small>{note}</small></div>;
}

export function ScopeNotice({ children, tone = "info" }: { children: ReactNode; tone?: string }) {
  return <div className={`scope-notice ${tone}`}><Icon name={tone === "danger" ? "alert" : "info"} /><div>{children}</div></div>;
}

export function EmptyView({ icon = "database", title, text, action }: { icon?: string; title: string; text: string; action?: ReactNode }) {
  return <div className="empty-state large"><span className="icon-tile"><Icon name={icon} size={24} /></span><h3>{title}</h3><p>{text}</p>{action}</div>;
}

export function ErrorView({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="inline-alert danger standalone"><Icon name="alert" /><span>{message}</span>{retry && <button className="btn btn-small btn-secondary" onClick={retry}>Retry</button>}</div>;
}

export function SeverityBadge({ value }: { value: string }) {
  const cls = value === "high" ? "danger" : value === "elevated" ? "warning" : value === "data_gap" ? "neutral" : "purple";
  return <span className={`severity-badge ${cls}`}><span />{value.replaceAll("_", " ")}</span>;
}

export function TimelineBars({ rows, height = 110 }: { rows: { bucket: string | null; count: number }[]; height?: number }) {
  if (!rows.length) return <div className="chart-empty">No timestamped observations</div>;
  const max = Math.max(...rows.map((row) => row.count), 1);
  const visible = rows.slice(-24);
  return <div className="timeline-chart" style={{ height }}>
    {visible.map((row, index) => <div className="timeline-column" key={`${row.bucket}-${index}`} title={`${row.bucket ? new Date(row.bucket).toLocaleString() : "undated"}: ${row.count}`}>
      <span className="timeline-value">{row.count || ""}</span>
      <div className="timeline-bar-track"><div className="timeline-bar" style={{ height: `${Math.max(row.count ? 8 : 2, (row.count / max) * 100)}%` }} /></div>
      {visible.length <= 12 && <small>{row.bucket ? new Date(row.bucket).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</small>}
    </div>)}
  </div>;
}

export function ScoreMeter({ score, coverage }: { score: number | null; coverage: number }) {
  return <div className="score-meter"><div className="score-meter-head"><strong>{score === null ? "—" : score.toFixed(1)}</strong><span>/ 100 heuristic</span></div><div className="meter-track"><div style={{ width: `${score || 0}%` }} /></div><small>Evidence coverage {(coverage * 100).toFixed(0)}% · not bot probability</small></div>;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Unknown";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}
