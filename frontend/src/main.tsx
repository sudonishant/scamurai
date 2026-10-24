import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import Icon from "./components/Icon";
import MatrixBackdrop from "./components/MatrixBackdrop";
import { api, ApiError, clearSession, getToken, setToken, UNAUTHORIZED_EVENT } from "./lib/api";
import "@fontsource/jetbrains-mono/latin-400.css";
import "@fontsource/jetbrains-mono/latin-500.css";
import "@fontsource/jetbrains-mono/latin-600.css";
import "@fontsource/jetbrains-mono/latin-700.css";
import "./index.css";

const ROLES = [
  { id: "owner", name: "Case owner", token: "dev-token-owner", detail: "Create, collect, analyse and export" },
  { id: "analyst", name: "Analyst", token: "dev-token-analyst", detail: "Collection and investigation workflows" },
  { id: "reviewer", name: "Reviewer", token: "dev-token-reviewer", detail: "Review findings and evidence decisions" },
  { id: "viewer", name: "Read-only viewer", token: "dev-token-viewer", detail: "Inspect without changing case data" },
];

function Login({ onAuth }: { onAuth: () => void }) {
  const [token, setTok] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function enterLive(value: string) {
    if (!value.trim()) { setError("Paste a token or choose a development role below."); return; }
    setBusy(true); setError("");
    setToken(value);
    try {
      await api.listCases();
      onAuth();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }

  return (
    <main className="login-page">
      <MatrixBackdrop />
      <header className="login-nav">
        <div className="brand"><span className="brand-mark"><Icon name="shield" size={22} /></span><span>SCAMURAI</span></div>
        <span className="quiet-label"><span className="live-dot" /> LIVE PUBLIC-SOURCE OSINT</span>
      </header>
      <section className="login-layout">
        <div className="login-hero">
          <div className="eyebrow">COORDINATED-DISINFORMATION INVESTIGATION LAB</div>
          <h1>SCAMURAI</h1>
          <p>Collect real public evidence. Connect narratives, accounts and infrastructure. Keep every source, limitation and review decision visible.</p>
          <div className="auth-card">
            <div className="auth-card-head"><div><h2>Sign in</h2><p>Access your live OSINT environment</p></div></div>
            <label className="field-label" htmlFor="token">Bearer token</label>
            <input id="token" value={token} onChange={(e) => setTok(e.target.value)} placeholder="dev-token-owner" autoComplete="off" spellCheck={false} aria-describedby="token-help" onKeyDown={(e) => { if (e.key === "Enter") enterLive(token); }} />
            <small id="token-help" className="field-help">Paste the token only, or paste “Bearer …”—the client normalizes it for you.</small>
            <button className="btn btn-primary btn-full" disabled={busy} onClick={() => enterLive(token)}>
              {busy ? <span className="spinner" /> : <Icon name="arrow" />} {busy ? "Connecting…" : "Open live workspace"}
            </button>
            {error && <div className="inline-alert danger" role="alert"><Icon name="alert" /><span>{error}</span></div>}
            <div className="auth-divider"><span>development quick access</span></div>
            <div className="role-list">{ROLES.map((role) => (
              <button key={role.id} onClick={() => { setTok(role.token); enterLive(role.token); }} disabled={busy}>
                <span><b>{role.name}</b><small>{role.detail}</small></span><Icon name="arrow" size={15} />
              </button>
            ))}</div>
            <p className="auth-note"><Icon name="info" size={14} /> Live API only. No synthetic demo, offline evidence fallback or fabricated source result.</p>
          </div>
          <div className="login-proof">
            <div><Icon name="database" /><span><b>Evidence preserved</b><small>Hash-snapshotted source observations</small></span></div>
            <div><Icon name="graph" /><span><b>Signals separated</b><small>Facts, hypotheses and unknowns</small></span></div>
            <div><Icon name="eye" /><span><b>Decisions stay human</b><small>Coverage beside every score</small></span></div>
          </div>
        </div>
      </section>
      <footer className="login-footer"><span>PUBLIC DATA ONLY</span><span>NO LOGIN BYPASS</span><span>NO SYNTHETIC DEMO</span></footer>
    </main>
  );
}

function Root() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  useEffect(() => {
    const handleUnauthorized = () => setAuthed(false);
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);
  if (!authed) return <Login onAuth={() => setAuthed(true)} />;
  return <App onLogout={() => { clearSession(); setAuthed(false); }} />;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><Root /></React.StrictMode>);
