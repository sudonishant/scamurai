import { useEffect, useState } from "react";
import { api, ApiError, isSandboxActive } from "../lib/api";
import type { Case } from "../lib/types";
import Icon from "./Icon";
import DataProvenanceBanner from "./DataProvenanceBanner";

const GOALS = [
  { id: "overview", icon: "activity", title: "Monitor a campaign", desc: "Narrative velocity, account clusters, geo patterns and explainable review cues from collected evidence.", tag: "CASE ANALYTICS" },
  { id: "check_post", icon: "narrative", title: "Verify a post or claim", desc: "Preserve public content, extract claims and inspect corroboration from authorized imports or official APIs.", tag: "IMPORT + API" },
  { id: "media", icon: "media", title: "Inspect media", desc: "Hashes, visual variants, metadata and pixel screening; optional local model output when configured.", tag: "LOCAL + MODEL" },
  { id: "osint", icon: "globe", title: "Investigate infrastructure", desc: "Live DNS, RDAP, web metadata, certificate history and archive evidence with per-source outcomes.", tag: "KEYLESS OSINT" },
];

export default function StartScreen({ onOpen }: { onOpen: (id: string, goal: string) => void }) {
  const [cases, setCases] = useState<Case[]>([]);
  const sandboxMode = isSandboxActive();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedGoal, setSelectedGoal] = useState("overview");
  const [form, setForm] = useState({ title: "", purpose: "", languages: "en,hi" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  async function load() {
    setLoading(true); setError("");
    try { setCases(await api.listCases()); }
    catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  function chooseGoal(goal: string) {
    setSelectedGoal(goal); setShowCreate(true); setError("");
  }

  async function createCase() {
    setCreating(true); setError("");
    try {
      const created = await api.createCase({
        title: form.title.trim(), purpose: form.purpose.trim(),
        languages: form.languages.split(",").map((s) => s.trim()).filter(Boolean),
      });
      onOpen(created.id, selectedGoal);
    } catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
    finally { setCreating(false); }
  }

  return (
    <div className="start-page">
      <DataProvenanceBanner />
      <section className="start-hero">
        <span className="eyebrow">{sandboxMode ? "SYNTHETIC PUBLIC DEMO" : "LIVE PUBLIC-SOURCE INTELLIGENCE"}</span>
        <h1>SCAMURAI</h1>
        <p>{sandboxMode ? "Explore the browser-only interface with fictional example cases. This preview is not a source of real-world findings." : "An evidence-first OSINT lab for coordinated-disinformation investigations. Real sources, connected evidence and visible uncertainty."}</p>
        <button className="btn btn-primary" onClick={() => chooseGoal("overview")}><Icon name="plus" />{sandboxMode ? "New preview case" : "New investigation"}</button>
      </section>

      <section className="start-heading">
        <div><span className="eyebrow">AVAILABLE WORKFLOWS</span><h2>{sandboxMode ? "Explore a sample workflow" : "Choose an investigation"}</h2><p>{sandboxMode ? "Workflows use fictional browser-preview records; no provider or social source is queried." : "Each workflow opens a scoped, case-isolated live workspace."}</p></div>
      </section>
      {error && !showCreate && <div className="inline-alert danger"><Icon name="alert" /><span>{error}</span><button className="btn btn-small btn-secondary" onClick={load}>Retry</button></div>}

      <section className="goal-grid">
        {GOALS.map((goal) => <button key={goal.id} className="goal-card" onClick={() => chooseGoal(goal.id)}>
          <div className="goal-card-top"><span className="icon-tile"><Icon name={goal.icon} /></span><span className="mini-tag">{sandboxMode ? "SYNTHETIC PREVIEW" : goal.tag}</span></div>
          <h3>{sandboxMode && goal.id === "check_post" ? "Explore a sample claim" : goal.title}</h3><p>{sandboxMode ? "Explore this workflow with fictional examples only; no real-world findings are produced." : goal.desc}</p>
          <span className="goal-action">{sandboxMode ? "Open preview scope" : "Define case scope"} <Icon name="arrow" size={15} /></span>
        </button>)}
      </section>

      <section className="method-strip">
        <div><span className="method-number">01</span><span><b>{sandboxMode ? "Preview" : "Collect"}</b><small>{sandboxMode ? "Fictional example data" : "Official APIs & authorized imports"}</small></span></div>
        <Icon name="arrow" />
        <div><span className="method-number">02</span><span><b>{sandboxMode ? "Inspect" : "Corroborate"}</b><small>{sandboxMode ? "Illustrative records only" : "Source states & evidence lineage"}</small></span></div>
        <Icon name="arrow" />
        <div><span className="method-number">03</span><span><b>Review</b><small>Signals, alternatives & unknowns</small></span></div>
      </section>

      <section className="cases-section">
        <div className="section-heading"><div><span className="eyebrow">{sandboxMode ? "BROWSER DEMO CASES · LOCAL ONLY" : "LIVE CASE INDEX"}</span><h2>Your investigations</h2><p>{cases.length} accessible investigation{cases.length === 1 ? "" : "s"}</p></div><button className="icon-button" onClick={load} title="Refresh cases"><Icon name="refresh" /></button></div>
        <div className="case-list">
          {loading ? <div className="empty-state compact"><span className="spinner dark" /> {sandboxMode ? "Loading browser preview…" : "Loading live cases…"}</div> : cases.length === 0 ? (
            <div className="empty-state"><span className="icon-tile"><Icon name="file" /></span><h3>No investigations yet</h3><p>{sandboxMode ? "Create a local preview case to explore the interface; it will not connect to a live backend." : "Choose a workflow above and define the authorized scope. Live cases are not populated with synthetic evidence."}</p></div>
          ) : cases.map((c) => <div key={c.id} className="case-row">
            <span className="case-icon"><Icon name="layers" /></span>
            <div className="case-main"><b>{c.title}</b>{sandboxMode && <span className="mini-tag case-demo-tag">SYNTHETIC · LOCAL ONLY</span>}<p>{c.purpose || "No purpose statement recorded"}</p><div className="case-meta"><span>{c.my_role}</span><span>{c.languages.join(" · ")}</span><span>{new Date(c.created_at).toLocaleDateString()}</span></div></div>
            <button className="btn btn-secondary" onClick={() => onOpen(c.id, "overview")}>{sandboxMode ? "Open preview" : "Open case"} <Icon name="arrow" size={15} /></button>
          </div>)}
        </div>
      </section>

      <section className="boundary-panel"><span className="eyebrow">WHAT IT DOESN'T DO</span><p>Scamurai does not bypass logins, read private messages, invent unavailable platform access, or turn a heuristic into an accusation. Source coverage and API requirements stay visible.</p></section>

      {showCreate && <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}>
        <div className="modal">
          <div className="modal-head"><div><span className="eyebrow">{sandboxMode ? "LOCAL PREVIEW" : "NEW CASE"}</span><h2>{sandboxMode ? "Create a preview case" : "Define investigation scope"}</h2></div><button className="icon-button" aria-label="Close new case" onClick={() => setShowCreate(false)}><Icon name="close" /></button></div>
          <p className="muted">{sandboxMode ? "This case stays in browser storage; it will not contact a source or connect to a backend. Do not enter private or sensitive data." : "Scope controls collection and interpretation. Defaults: 5 seed URLs, depth 2, 200 entities and 20 source fetches, clamped server-side."}</p>
          <div className="field"><label>Case title</label><input autoFocus value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder={sandboxMode ? "e.g. Sample flood scenario" : "e.g. Regional flood narrative — October"} /></div>
          <div className="field"><label>{sandboxMode ? "Preview note (optional)" : "Purpose and authorized scope"}</label><textarea rows={4} value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} placeholder={sandboxMode ? "Optional note for your local preview case" : "Which public sources, hashtags, URLs or authorized exports are in scope?"} /></div>
          <div className="field"><label>Languages (comma separated)</label><input value={form.languages} onChange={(e) => setForm({ ...form, languages: e.target.value })} /></div>
          <div className="inline-alert"><Icon name="shield" /><span>{sandboxMode ? "This preview does not access sources and is not for private or sensitive information." : "Use public information and authorized exports only. Do not upload unlawfully obtained personal data."}</span></div>
          {error && <div className="inline-alert danger"><Icon name="alert" /><span>{error}</span></div>}
          <div className="modal-actions"><button className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button><button className="btn btn-primary" disabled={creating || !form.title.trim()} onClick={createCase}>{creating ? <span className="spinner" /> : <Icon name="plus" />}{creating ? "Creating…" : sandboxMode ? "Create preview case" : "Create investigation"}</button></div>
        </div>
      </div>}
    </div>
  );
}
