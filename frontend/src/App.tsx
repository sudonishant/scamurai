import { useState } from "react";
import StartScreen from "./components/StartScreen";
import Workspace from "./components/Workspace";
import Icon from "./components/Icon";
import MatrixBackdrop from "./components/MatrixBackdrop";
import { getApiUrl, setApiUrl } from "./lib/api";

interface Props { onLogout: () => void }

export default function App({ onLogout }: Props) {
  const [openCase, setOpenCase] = useState<string | null>(null);
  const [goal, setGoal] = useState("overview");
  if (!openCase) {
    return <div className="app"><MatrixBackdrop /><TopBar onLogout={onLogout} /><StartScreen onOpen={(id, g) => { setGoal(g); setOpenCase(id); }} /></div>;
  }
  return <div className="app"><MatrixBackdrop /><TopBar onLogout={onLogout} onHome={() => setOpenCase(null)} /><Workspace caseId={openCase} initialGoal={goal} /></div>;
}

function TopBar({ onLogout, onHome }: { onLogout: () => void; onHome?: () => void }) {
  const [apiUrl, setUrl] = useState(getApiUrl());
  const [showConfig, setShowConfig] = useState(false);
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
            <p className="muted">Live mode uses the same origin by default, with the Vite server proxying <code>/api</code> to FastAPI. Set a remote HTTPS API only for a separately deployed backend.</p>
            <div className="field"><label>FastAPI base URL (optional)</label><input value={apiUrl} onChange={(e) => setUrl(e.target.value)} placeholder="https://api.your-domain.org" /></div>
            <div className="inline-alert"><Icon name="info" /><span>In a hosted preview, do not use <code>localhost</code> or <code>127.0.0.1</code> in browser code. Leave this blank for the built-in proxy.</span></div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => { setUrl(""); setApiUrl(""); window.location.reload(); }}>Use same-origin live API</button>
              <button className="btn btn-primary" onClick={() => { setApiUrl(apiUrl); window.location.reload(); }}>Save live connection</button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
