import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { CommentRow } from "../lib/types";

export default function CommentsView({ caseId, onChanged }: { caseId: string; onChanged: () => void }) {
  const [items, setItems] = useState<CommentRow[]>([]);
  const [coverage, setCoverage] = useState<unknown[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");

  async function load() {
    const body = await api.comments(caseId, q);
    setItems(body.items);
    setCoverage(body.coverage);
    setTotal(body.total);
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [caseId, q]);

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
      <input placeholder="Filter text…" value={q} onChange={(e) => setQ(e.target.value)} style={{ marginBottom: 10 }} />
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
                <button className="btn secondary" onClick={async () => {
                  await api.analyzeComment(caseId, c.id); onChanged(); load();
                }}>Explain</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
