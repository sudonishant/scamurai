import { useEffect, useState } from "react";
import StartScreen from "./components/StartScreen";
import Workspace from "./components/Workspace";
import Icon from "./components/Icon";
import MatrixBackdrop from "./components/MatrixBackdrop";
import { getApiUrl, setApiUrl } from "./lib/api";

interface Props { onLogout: () => void }

export default function App({ onLogout }: Props) {
  const [openCase, setOpenCase] = useState<string | null>(() => new URLSearchParams(window.location.search).get("case"));
  const [goal, setGoal] = useState("overview");

  useEffect(() => {
    const restore = () => setOpenCase(new URLSearchParams(window.location.search).get("case"));
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);

  function openInvestigation(id: string, selectedGoal: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("case", id);
    ["tab", "account", "alert", "post", "finding", "evidence"].forEach((key) => url.searchParams.delete(key));
    window.history.pushState({ caseId: id }, "", url);
    setGoal(selectedGoal); setOpenCase(id);
  }

  function goHome() {
    const url = new URL(window.location.href);
    ["case", "tab", "account", "alert", "post", "finding", "evidence"].forEach((key) => url.searchParams.delete(key));
    window.history.pushState({}, "", url);
    setOpenCase(null);
  }

  if (!openCase) {
    return <div className="app"><MatrixBackdrop /><TopBar onLogout={onLogout} onHome={goHome} /><StartScreen onOpen={openInvestigation} /></div>;
  }
  return <div className="app"><MatrixBackdrop /><TopBar onLogout={onLogout} onHome={goHome} /><Workspace key={openCase} caseId={openCase} initialGoal={goal} /></div>;
}

function TopBar({ onLogout, onHome }: { onLogout: () => void; onHome?: () => void }) {
  const [apiUrl, setUrl] = useState(getApiUrl());
  const [showConfig, setShowConfig] = useState(false);
  const [configError, setConfigError] = useState("");

  function saveConnection() {
    try {
      const clean = setApiUrl(apiUrl);
      setUrl(clean);
      window.location.reload();
    } catch (e) {
      setConfigError(e instanceof Error ? e.message : String(e));
    }
  }
  return (
    <header className="topbar">
      <button className="brand brand-button" onClick={onHome} title="Investigation home">
        <span className="brand-mark"><Icon name="shield" size={20} /></span><span>SCAMURAI</span>
      </button>
      <span className="topbar-divider" />
      <span className="product-label">OSINT INVESTIGATION LAB</span>
      <span className="spacer" />
      <button className="connection-pill live" onClick={() => setShowConfig(true)}>
        <span className="live-dot" />{getApiUrl() ? "Remote live API" : "Same-origin live API"}<Icon name="settings" size={14} />
      </button>
      {onHome && <button className="icon-button" onClick={onHome} title="All investigations"><Icon name="home" /></button>}
      <button className="btn btn-quiet" onClick={onLogout}><Icon name="logout" size={16} /> Switch role</button>
      {showConfig && (
        <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && setShowConfig(false)}>
          <div className="modal config-modal">
            <div className="modal-head"><div><span className="eyebrow">CONNECTION</span><h2>API configuration</h2></div><button className="icon-button" onClick={() => setShowConfig(false)}><Icon name="close" /></button></div>
            <p className="muted">Live mode uses the same origin by default, with the Vite server proxying <code>/api</code> to FastAPI. On a static host, set a separately deployed HTTPS FastAPI base URL and allow this UI origin in backend CORS.</p>
            <div className="field"><label>FastAPI base URL (optional)</label><input value={apiUrl} onChange={(e) => setUrl(e.target.value)} placeholder="https://api.your-domain.org" autoComplete="url" /></div>
            <div className="inline-alert"><Icon name="info" /><span>In a hosted preview, do not use <code>localhost</code> or <code>127.0.0.1</code> in browser code. Leave this blank for the built-in development proxy.</span></div>
            {configError && <div className="inline-alert danger" role="alert"><Icon name="alert" /><span>{configError}</span></div>}
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => { setUrl(""); setApiUrl(""); window.location.reload(); }}>Use same-origin live API</button>
              <button className="btn btn-primary" onClick={saveConnection}>Save live connection</button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
