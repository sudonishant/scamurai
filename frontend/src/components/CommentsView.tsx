import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { CommentRow } from "../lib/types";

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function CommentsView({ caseId, onChanged }: { caseId: string; onChanged: () => void }) {
  const [items, setItems] = useState<CommentRow[]>([]);
  const [coverage, setCoverage] = useState<unknown[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [analyzingId, setAnalyzingId] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setQ(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api.comments(caseId, q)
      .then((body) => {
        if (!active) return;
        setItems(body.items);
        setCoverage(body.coverage);
        setTotal(body.total);
      })
      .catch((e: unknown) => { if (active) setError(message(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [caseId, q, retry]);

  async function analyze(commentId: string) {
    setAnalyzingId(commentId);
    setActionError("");
    try {
      await api.analyzeComment(caseId, commentId);
      setRetry((value) => value + 1);
      onChanged();
    } catch (e) {
      setActionError(message(e));
    } finally {
      setAnalyzingId("");
    }
  }

  return (
    <div className="scroll" style={{ padding: 14, height: "100%", overflow: "auto" }}>
      <h3>Comment corpus · {total} unique collected</h3>
      {coverage.map((c, i) => (
        <div key={i} className="coverage">
          <b>Coverage statement</b>
          <pre className="mono" style={{ margin: "6px 0 0" }}>{JSON.stringify(c, null, 2)}</pre>
          <div className="muted" style={{ fontSize: 12 }}>
            Unknown completeness is never shown as 100%; non-comparable denominators stay unpercentaged.
          </div>
        </div>
      ))}
      <input aria-label="Filter comments" placeholder="Filter text…" value={query} onChange={(e) => setQuery(e.target.value)} style={{ marginBottom: 10 }} />
      {loading && <p className="muted" role="status">Loading comments…</p>}
      {error && <div className="inline-alert danger" role="alert"><span>{error}</span><button className="btn btn-small btn-secondary" onClick={() => setRetry((value) => value + 1)}>Retry</button></div>}
      {actionError && <div className="inline-alert danger" role="alert">Could not analyze comment: {actionError}</div>}
      {!loading && !error && items.length === 0 && <p className="muted">No comments match this filter.</p>}
      <table>
        <thead>
          <tr><th>Comment</th><th>Author</th><th>Time / precision</th><th>Link</th><th>Analysis</th><th></th></tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id}>
              <td style={{ maxWidth: 320 }}>
                {c.raw_text}
                {c.uncertain_duplicate && <span className="badge warn" style={{ marginLeft: 6 }}>uncertain dup</span>}
              </td>
              <td>{c.author_ref}</td>
              <td className="muted">
                {c.timestamp ? new Date(c.timestamp).toISOString() : "—"}
                <div>{c.timestamp_precision}</div>
              </td>
              <td>
                {c.permalink
                  ? <a href={c.permalink} target="_blank" rel="noreferrer">open original comment</a>
                  : <span className="badge">unavailable ({c.permalink_status})</span>}
              </td>
              <td>
                {c.analysis ? (
                  <div className="pill-row">
                    {c.analysis.categories.map((cat) => (
                      <span key={cat} className={`badge ${cat.includes("insult") || cat.includes("threat") ? "err" : "similarity"}`}>
                        {cat.replaceAll("_", " ")}
                      </span>
                    ))}
                    <div className="muted" style={{ fontSize: 11 }}>{c.analysis.validation_status}</div>
                  </div>
                ) : <span className="muted">not analyzed</span>}
              </td>
              <td>
                <button className="btn secondary" disabled={!!analyzingId} onClick={() => analyze(c.id)}>
                  {analyzingId === c.id ? "Analyzing…" : "Explain"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
