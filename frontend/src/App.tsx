import { useState } from "react";
import StartScreen from "./components/StartScreen";
import Workspace from "./components/Workspace";
import { getApiUrl, setApiUrl } from "./lib/api";

interface Props { onLogout: () => void }

export default function App({ onLogout }: Props) {
  const [openCase, setOpenCase] = useState<string | null>(null);
  const [goal, setGoal] = useState("check_post");

  if (!openCase) {
    return (
      <div className="app">
        <TopBar onLogout={onLogout} />
        <StartScreen onOpen={(id, g) => { setGoal(g); setOpenCase(id); }} />
      </div>
    );
  }
  return (
    <div className="app">
      <TopBar onLogout={onLogout} onHome={() => setOpenCase(null)} />
      <Workspace caseId={openCase} initialGoal={goal} />
    </div>
  );
}

function TopBar({ onLogout, onHome }: { onLogout: () => void; onHome?: () => void }) {
  const [apiUrl, setUrl] = useState(getApiUrl());
  const [showConfig, setShowConfig] = useState(false);

  return (
    <header className="topbar">
      <h1 style={{ cursor: onHome ? "pointer" : "default" }} onClick={onHome}>
        🕵️ Scamurai Evidence Workspace
      </h1>
      <span className="spacer" />
      <button
        className="badge"
        style={{ cursor: "pointer", background: apiUrl ? "#134e4a" : "#27272a", border: "1px solid #444" }}
        onClick={() => setShowConfig(!showConfig)}
        title="Configure backend API endpoint"
      >
        {apiUrl ? `🟢 API: ${apiUrl}` : "⚡ Demo Mode (Offline)"}
      </button>
      <span className="badge">three outputs: established · signal · unknown</span>
      <button className="btn secondary" onClick={onLogout}>Switch role</button>

      {showConfig && (
        <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && setShowConfig(false)}>
          <div className="modal" style={{ maxWidth: 450 }}>
            <h3>Backend API Configuration</h3>
            <p className="muted">
              Leave blank to use built-in realistic demo data (ideal for GitHub Pages and client demos), or enter your live FastAPI URL (e.g. <code>http://127.0.0.1:8000</code>).
            </p>
            <div className="field">
              <label>FastAPI Backend URL</label>
              <input
                value={apiUrl}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="http://127.0.0.1:8000"
              />
            </div>
            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn" onClick={() => { setApiUrl(apiUrl); setShowConfig(false); window.location.reload(); }}>
                Save & Reload
              </button>
              <button className="btn secondary" onClick={() => { setUrl(""); setApiUrl(""); setShowConfig(false); window.location.reload(); }}>
                Reset to Demo Mode
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
