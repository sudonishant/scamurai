import { useState } from "react";
import StartScreen from "./components/StartScreen";
import Workspace from "./components/Workspace";

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
  return (
    <header className="topbar">
      <h1 style={{ cursor: onHome ? "pointer" : "default" }} onClick={onHome}>
        🕵️ PS-03 Evidence Workspace
      </h1>
      <span className="spacer" />
      <span className="badge">three outputs: established · signal · unknown</span>
      <button className="btn secondary" onClick={onLogout}>Switch role</button>
    </header>
  );
}
