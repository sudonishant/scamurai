import { useMemo, useState } from "react";
import { api } from "../lib/api";
import type { GraphData } from "../lib/types";

interface Pair {
  pair: string[];
  identity_verified: boolean;
  shared_content: string[];
  explicit_public_crosslinks: boolean;
  timing_indicators: string;
  contradictory_or_insufficient: string[];
}

export default function CompareView({ caseId, graph }: { caseId: string; graph: GraphData }) {
  const accounts = useMemo(
    () => graph.nodes.filter((n) => n.entity_type === "account"),
    [graph],
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [error, setError] = useState("");

  function toggle(id: string) {
    setSelected((prev) => prev.includes(id)
      ? prev.filter((x) => x !== id)
      : prev.length >= 4 ? prev : [...prev, id]);
  }

  async function compare() {
    setError("");
    try {
      const body = await api.compare(caseId, selected) as { pairs: Pair[]; disclaimer: string };
      setPairs(body.pairs);
    } catch (e) { setError(String(e)); }
  }

  return (
    <div className="scroll" style={{ padding: 14, height: "100%", overflow: "auto" }}>
      <h3>Account comparison — link analysis, not identity resolution</h3>
      <p className="muted">Select 2–4 accounts. Four accounts produce six distinct pairs.</p>
      <div className="pill-row">
        {accounts.map((a) => (
          <button key={a.id}
            className={`badge ${selected.includes(a.entity_id) ? "similarity" : ""}`}
            onClick={() => toggle(a.entity_id)}>
            {a.label}
          </button>
        ))}
      </div>
      <button className="btn" disabled={selected.length < 2} onClick={compare}>
        Build pairwise matrix ({(selected.length * (selected.length - 1)) / 2} pairs)
      </button>
      {error && <p className="badge err">{error}</p>}
      {pairs.map((p, i) => (
        <div key={i} className="compare-pair">
          <b>{p.pair[0]} ↔ {p.pair[1]}</b>
          {!p.identity_verified && <span className="badge warn" style={{ marginLeft: 8 }}>identity not verified</span>}
          <h4>Shared content</h4>
          {p.shared_content.length ? p.shared_content.map((s, j) => <div key={j} className="mono muted">{s}</div>)
            : <div className="muted">none</div>}
          <h4>Explicit public cross-links: {p.explicit_public_crosslinks ? "yes (source-attributed)" : "none"}</h4>
          <h4>Timing</h4><div className="muted">{p.timing_indicators}</div>
          <h4>Contradictory / insufficient</h4>
          {p.contradictory_or_insufficient.map((c, j) => <div key={j} className="limitation">▸ {c}</div>)}
        </div>
      ))}
    </div>
  );
}
