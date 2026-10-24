import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Capability } from "../lib/types";
import Icon from "./Icon";
import { PageHeader, ScopeNotice } from "./AnalyticsPrimitives";

const ACCESS_ROWS = [
  { capability: "Authorized JSON, CSV, text and image imports", access: "NO API KEY", tone: "keyless", reality: "User-supplied authorized evidence; this is not live platform collection." },
  { capability: "DNS, RDAP, web metadata, CT and Wayback", access: "NO API KEY", tone: "keyless", reality: "Real bounded public requests; provider availability and rate limits still apply." },
  { capability: "Mastodon public hashtag timelines", access: "KEYLESS IF PERMITTED", tone: "keyless", reality: "Official instance API; one public page when the instance allows public preview." },
  { capability: "Narratives, network, geo and early warnings", access: "NO API KEY", tone: "keyless", reality: "Computed locally from the current collected case corpus; not a platform firehose." },
  { capability: "Hashes, metadata and pixel screening", access: "NO API KEY", tone: "keyless", reality: "Deterministic local observations; no standalone manipulation verdict." },
  { capability: "YouTube public comments and replies", access: "API KEY REQUIRED", tone: "key", reality: "Set SCAMURAI_YOUTUBE_API_KEY; official Data API v3 quota is required." },
  { capability: "Published Google fact-check search", access: "API KEY REQUIRED", tone: "key", reality: "Set SCAMURAI_GOOGLE_FACTCHECK_API_KEY; no match never proves a claim false." },
  { capability: "External LLM for the bounded agent", access: "OPTIONAL API KEY", tone: "key", reality: "Local deterministic tools need no LLM; Groq, Gemini or OpenRouter need server-side credentials." },
  { capability: "Synthetic-image classifier", access: "LOCAL MODEL", tone: "model", reality: "No API key by default; configure a real Hugging Face model and optional dependencies. Output is uncalibrated." },
  { capability: "Instagram, Facebook and Reddit", access: "OFFICIAL ACCESS", tone: "limited", reality: "Reviewed OAuth/permissions or approval is required; live collection is not claimed when unconfigured." },
  { capability: "OCR, reverse image search and video deepfakes", access: "NOT AVAILABLE", tone: "limited", reality: "No working provider/pipeline is configured; no substitute result is generated." },
];

export default function ConnectorsView({ caseId, role, onChanged }: { caseId: string; role: string; onChanged: () => void }) {
  const [caps, setCaps] = useState<Capability[]>([]);
  const [ytUrl, setYtUrl] = useState("");
  const [ytResult, setYtResult] = useState<Record<string, any> | null>(null);
  const [fcQuery, setFcQuery] = useState("");
  const [fcResult, setFcResult] = useState<Record<string, any> | null>(null);
  const [instance, setInstance] = useState("mastodon.social");
  const [hashtag, setHashtag] = useState("");
  const [mastodonResult, setMastodonResult] = useState<Record<string, any> | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const canRun = ["owner", "analyst"].includes(role);
  const refresh = useCallback(() => { api.capabilities(caseId).then(setCaps).catch((e) => setError(e instanceof ApiError ? e.message : String(e))); }, [caseId]);
  useEffect(refresh, [refresh]);
  const cap = (provider: string) => caps.find((c) => c.provider === provider);

  async function guard(key: string, fn: () => Promise<void>) {
    setBusy(key); setError("");
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
    finally { setBusy(""); }
  }

  return <div className="view-page narrow-view">
    <PageHeader eyebrow="COLLECTION & PROVIDERS" title="Live connectors" description="Official APIs and authorized imports with explicit access, quota and coverage states." />
    <ScopeNotice>API keys stay in server-side <code>.env</code>. A 401, 403, 429 or transport failure is never converted into “no results”. Public access does not imply unlimited redistribution or platform-wide coverage.</ScopeNotice>
    {error && <div className="inline-alert danger"><Icon name="alert" /><span>{error}</span></div>}
    <section className="card access-card"><div className="card-head"><div><span className="eyebrow">BEFORE YOU INVESTIGATE</span><h2>API & access requirements</h2><p>Exactly what works keyless, what needs credentials, and what is unavailable.</p></div></div>
      <div className="access-table" role="table" aria-label="API and access requirements">
        <div className="access-table-head" role="row"><span>CAPABILITY</span><span>ACCESS</span><span>ACTUAL BEHAVIOR</span></div>
        {ACCESS_ROWS.map((row) => <div className="access-row" role="row" key={row.capability}><b>{row.capability}</b><span className={`access-badge ${row.tone}`}>{row.access}</span><p>{row.reality}</p></div>)}
      </div>
    </section>
    <section className="card"><div className="card-head"><div><span className="eyebrow">CAPABILITY MATRIX</span><h2>Source health</h2></div><button className="icon-button" onClick={refresh}><Icon name="refresh" /></button></div><div className="capability-grid">{caps.map((item) => <div className="capability-card" key={item.provider}><div><b>{item.provider}</b><span className={`source-status ${item.configured ? "good" : "limited"}`}><span />{item.status.replaceAll("_", " ")}</span></div><p>{item.detail}</p><div className="feature-tags">{item.operations.map((operation) => <span key={operation}>{operation.replaceAll("_", " ")}</span>)}</div></div>)}</div></section>

    <section className="card connector-card"><div className="connector-heading"><span className="icon-tile"><Icon name="narrative" /></span><div><h2>Mastodon public hashtag timeline</h2><p>Official instance REST API · no key when public preview is enabled · one bounded page</p></div><span className="mini-tag">KEYLESS WHEN PERMITTED</span></div>
      <div className="form-grid two"><div className="field"><label>Public instance</label><input value={instance} onChange={(e) => setInstance(e.target.value)} disabled={!canRun || !!busy} placeholder="mastodon.social" /></div><div className="field"><label>Hashtag (without #)</label><input value={hashtag} onChange={(e) => setHashtag(e.target.value)} disabled={!canRun || !!busy} placeholder="disinformation" /></div></div>
      <button className="btn btn-primary" disabled={!canRun || !!busy || !hashtag.trim() || !instance.trim()} onClick={() => guard("mastodon", async () => { setMastodonResult(null); const result = await api.mastodonImport(caseId, instance, hashtag); setMastodonResult(result); onChanged(); })}>{busy === "mastodon" ? <span className="spinner" /> : <Icon name="download" />} {busy === "mastodon" ? "Collecting public page…" : "Import public timeline"}</button>
      {mastodonResult && <div className="result-callout"><Icon name="check" /><div><b>{mastodonResult.posts} new posts · {mastodonResult.accounts} accounts · {mastodonResult.geo_observations || 0} geo observations</b><p>{mastodonResult.coverage}</p><small>{mastodonResult.statuses_returned} statuses returned · {mastodonResult.skipped_reblogs} reblogs excluded</small></div></div>}
    </section>

    <section className="card connector-card"><div className="connector-heading"><span className="icon-tile"><Icon name="media" /></span><div><h2>YouTube public comments</h2><p>Official Data API v3 · key and quota required · replies and coverage state preserved</p></div>{cap("youtube") && <span className={`source-status ${cap("youtube")!.configured ? "good" : "limited"}`}><span />{cap("youtube")!.status.replaceAll("_", " ")}</span>}</div>
      <div className="inline-form"><input value={ytUrl} onChange={(e) => setYtUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=… or 11-character video ID" disabled={!canRun || !!busy} /><button className="btn btn-secondary" disabled={!canRun || !!busy || ytUrl.trim().length < 11} onClick={() => guard("youtube", async () => { setYtResult(null); setYtResult(await api.youtubeImport(caseId, ytUrl)); onChanged(); })}>{busy === "youtube" ? "Importing…" : "Import comments"}</button></div>
      {!cap("youtube")?.configured && <p className="limitation">Set <code>SCAMURAI_YOUTUBE_API_KEY</code> (legacy <code>PS03_YOUTUBE_API_KEY</code> also works) on the backend.</p>}
      {ytResult && <div className="result-callout"><Icon name="check" /><div><b>{ytResult.comments_created} new comments imported</b><p>Coverage: {ytResult.coverage?.status} · {ytResult.uncertain_duplicates_held} uncertain duplicates held</p></div></div>}
    </section>

    <section className="card connector-card"><div className="connector-heading"><span className="icon-tile"><Icon name="check" /></span><div><h2>Published fact-check search</h2><p>Google Fact Check Tools Claim Search · no result never means false</p></div>{cap("factcheck") && <span className={`source-status ${cap("factcheck")!.configured ? "good" : "limited"}`}><span />{cap("factcheck")!.status.replaceAll("_", " ")}</span>}</div>
      <div className="inline-form"><input value={fcQuery} onChange={(e) => setFcQuery(e.target.value)} placeholder="Claim text to find matching published reviews…" disabled={!canRun || !!busy} /><button className="btn btn-secondary" disabled={!canRun || !!busy || fcQuery.trim().length < 3} onClick={() => guard("factcheck", async () => { setFcResult(null); setFcResult(await api.factcheckSearch(caseId, fcQuery)); })}>{busy === "factcheck" ? "Searching…" : "Search reviews"}</button></div>
      {fcResult && <div className="factcheck-results"><p className="muted">{fcResult.note}</p>{!fcResult.matches?.length && <div className="empty-inline"><Icon name="info" />No matching published review returned. Claim truth remains undetermined.</div>}{(fcResult.matches || []).map((match: any, index: number) => <div className="evidence-chain" key={index}><b>{match.claim}</b><p>{match.outcome || "Unrated"} · {match.source}</p>{match.url && <a href={match.url} target="_blank" rel="noreferrer">Open review <Icon name="external" size={12} /></a>}</div>)}</div>}
    </section>

    <details className="methodology-note"><summary><Icon name="info" /> What the local MCP server does—and does not do</summary><p>The MCP server exposes local media, comment, coordination and claim-analysis functions to an AI client. It does <b>not</b> replace platform API authorization or turn an LLM into a live data source.</p><pre>python backend/scamurai_mcp.py</pre></details>
  </div>;
}
