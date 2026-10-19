import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { api, getToken, setToken } from "./lib/api";
import "./index.css";

function Login() {
  const [users, setUsers] = useState<{ email: string; name: string; token_hint: string }[]>([]);
  const [token, setTok] = useState(getToken() || "");

  useEffect(() => { api.users().then(setUsers).catch(() => setUsers([])); }, []);

  return (
    <div className="start">
      <h1>Sign in (development demo)</h1>
      <p className="muted">
        Demo tokens map to RBAC roles. Replace this screen with your identity provider before deployment.
      </p>
      <div className="case-list">
        {users.map((u) => (
          <div key={u.email} className="case-row">
            <div><b>{u.name}</b><div className="muted mono">{u.email}</div></div>
            <button className="btn" onClick={() => { setToken(u.token_hint); setTok(u.token_hint); }}>
              Use role
            </button>
          </div>
        ))}
      </div>
      <div className="field" style={{ marginTop: 18 }}>
        <label>Or paste a bearer token</label>
        <div className="row">
          <input value={token} onChange={(e) => setTok(e.target.value)} placeholder="dev-token-owner" />
          <button className="btn secondary" onClick={() => setToken(token)}>Save</button>
        </div>
      </div>
    </div>
  );
}

function Root() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  useEffect(() => {
    const handler = () => setAuthed(Boolean(getToken()));
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);
  if (!authed) return <Login />;
  return <App onLogout={() => { localStorage.clear(); setAuthed(false); }} />;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><Root /></React.StrictMode>,
);
