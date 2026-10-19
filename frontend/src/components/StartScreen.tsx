import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Case } from "../lib/types";

const GOALS = [
  { id: "check_post", icon: "🔗", title: "Check a post", desc: "Submit a public post URL or its text and trace the evidence." },
  { id: "image_source", icon: "🖼️", title: "Find an image's source", desc: "Exact hashes, perceptual variants, crops and reverse search status." },
  { id: "photo_location", icon: "📍", title: "Estimate photo location", desc: "EXIF plus background clues — no invented pins, narrowest precision only." },
  { id: "comments", icon: "💬", title: "Analyze comments", desc: "Multilabel Hindi/English/Hinglish analysis with honest coverage." },
  { id: "compare", icon: "🔀", title: "Compare accounts", desc: "Pairwise matrix of shared content, cross-links and timing." },
  { id: "coordination", icon: "🕸️", title: "Investigate possible coordination", desc: "Repeated aligned behavior across episodes — not an accusation engine." },
  { id: "empty_graph", icon: "🧩", title: "Start an empty graph", desc: "Expert mode: build the investigation one transform at a time." },
];

interface Props {
  onOpen: (id: string, goal: string) => void;
}

export default function StartScreen({ onOpen }: Props) {
  const [cases, setCases] = useState<Case[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: "", purpose: "", languages: "en,hi" });
  const [error, setError] = useState("");

  async function load() {
    try { setCases(await api.listCases()); } catch { setCases([]); }
  }
  useEffect(() => { load(); }, []);

  async function createCase(goal: string) {
    setError("");
    try {
      const created = await api.createCase({
        title: form.title || "Untitled investigation",
        purpose: form.purpose,
        languages: form.languages.split(",").map((s) => s.trim()).filter(Boolean),
      });
      onOpen(created.id, goal);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="start">
      <h1>Scamurai · Coordinated Disinformation Detection</h1>
      <p className="muted">
        Evidence-first investigation workspace. Every conclusion answers:
        <b> what is established, what is a signal, and what remains unknown.</b>
      </p>

      <div className="goal-grid">
        {GOALS.map((g) => (
          <button key={g.id} className="goal-card" onClick={() => setShowCreate(true)}>
            <span className="icon">{g.icon}</span>
            <h3>{g.title}</h3>
            <p>{g.desc}</p>
          </button>
        ))}
      </div>

      <h2>Your cases</h2>
      <div className="case-list">
        {cases.length === 0 && <p className="muted">No cases yet — choose a goal above to begin.</p>}
        {cases.map((c) => (
          <div key={c.id} className="case-row">
            <div>
              <b>{c.title}</b>
              <div className="muted">{c.purpose || "No purpose stated"} · role: {c.my_role}</div>
            </div>
            <button className="btn" onClick={() => onOpen(c.id, "check_post")}>Open</button>
          </div>
        ))}
      </div>

      {showCreate && (
        <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}>
          <div className="modal">
            <h2>Define case scope</h2>
            <p className="muted">
              Default guardrails: max 5 seed URLs, depth 2, 200 new entities, 20 fetches,
              10-minute deadline — clamped server-side.
            </p>
            <div className="field">
              <label>Case title</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Investigating the rain photo" />
            </div>
            <div className="field">
              <label>Purpose and scope</label>
              <textarea rows={3} value={form.purpose}
                onChange={(e) => setForm({ ...form, purpose: e.target.value })}
                placeholder="Up to these four links and permitted public search results." />
            </div>
            <div className="field">
              <label>Languages (comma separated)</label>
              <input value={form.languages}
                onChange={(e) => setForm({ ...form, languages: e.target.value })} />
            </div>
            {error && <p className="badge err">{error}</p>}
            <div className="row">
              <button className="btn secondary" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn" onClick={() => createCase("check_post")}>Create case</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
