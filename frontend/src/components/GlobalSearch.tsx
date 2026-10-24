import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { SearchResponse, SearchResult } from "../lib/types";
import Icon from "./Icon";

export default function GlobalSearch({ caseId, onSelect }: {
  caseId: string;
  onSelect: (target: SearchResult["target"]) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  useEffect(() => {
    const clean = query.trim();
    if (clean.length < 2) {
      setResults(null);
      setError("");
      setLoading(false);
      return;
    }
    let current = true;
    setLoading(true);
    setError("");
    const timer = window.setTimeout(async () => {
      try {
        const response = await api.search(caseId, clean);
        if (current) { setResults(response); setOpen(true); }
      } catch (reason) {
        if (current) setError(reason instanceof ApiError ? reason.message : String(reason));
      } finally {
        if (current) setLoading(false);
      }
    }, 280);
    return () => { current = false; window.clearTimeout(timer); };
  }, [caseId, query]);

  return <div className="global-search" ref={root}>
    <Icon name="search" size={16} />
    <input
      aria-label="Search this investigation"
      value={query}
      onFocus={() => setOpen(true)}
      onKeyDown={(event) => { if (event.key === "Escape") { setOpen(false); event.currentTarget.blur(); } }}
      onChange={(event) => setQuery(event.target.value)}
      placeholder="Search accounts, posts, evidence, alerts…"
    />
    {loading && <span className="spinner dark" aria-label="Searching" />}
    {query && !loading && <button className="search-clear" aria-label="Clear search" onClick={() => { setQuery(""); setResults(null); }}><Icon name="close" size={14} /></button>}
    {open && (query.trim().length >= 2) && <div className="global-search-results" id="case-search-results">
      {error && <div className="search-message" role="alert">{error}</div>}
      {!error && !loading && results?.total === 0 && <div className="search-message">No case-scoped matches for “{results.query}”.</div>}
      {!error && results?.groups.map((group) => <section key={group.type}>
        <span className="search-group-label">{group.type} · {group.items.length}</span>
        {group.items.map((item) => <button key={`${group.type}-${item.id}`} onClick={() => { onSelect(item.target); setOpen(false); }}>
          <span className={`search-type-icon ${group.type}`}><Icon name={group.type === "accounts" ? "users" : group.type === "alerts" ? "alert" : group.type === "evidence" ? "database" : group.type === "findings" ? "check" : "narrative"} size={15} /></span>
          <span><b>{item.title}</b><small>{item.snippet}</small></span><Icon name="arrow" size={14} />
        </button>)}
      </section>)}
      {results && <footer>{results.scope}</footer>}
    </div>}
  </div>;
}
