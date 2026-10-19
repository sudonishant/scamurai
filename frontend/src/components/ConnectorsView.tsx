import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Capability } from "../lib/types";

type YtResult = {
  video_id: string;
  comments_created: number;
  uncertain_duplicates_held: number;
  coverage: { status: string; unique_collected: number; platform_displayed_count: number | null };
};

type FcResult = {
  query: string;
  note: string;
  matches: { claim: string; claimant: string; outcome: string; source: string; url: string; claim_date?: string }[];
};

export default function ConnectorsView({ caseId, role, onChanged }: {
  caseId: string; role: string; onChanged: () => void;
}) {
  const [caps, setCaps] = useState<Capability[]>([]);
  const [ytUrl, setYtUrl] = useState("");
  const [ytResult, setYtResult] = useState<YtResult | null>(null);
  const [fcQuery, setFcQuery] = useState("");
  const [fcResult, setFcResult] = useState<FcResult | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const canRun = ["owner", "analyst"].includes(role);

  const refresh = useCallback(() => {
    api.capabilities(caseId).then(setCaps).catch(() => setCaps([]));
  }, [caseId]);
  useEffect(refresh, [refresh]);

  const cap = (provider: string) => caps.find((c) => c.provider === provider);

  async function importYoutube() {
    setBusy("yt"); setError(""); setYtResult(null);
    try {
      setYtResult(await api.youtubeImport(caseId, ytUrl));
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(""); }
  }

  async function factCheck() {
    setBusy("fc"); setError(""); setFcResult(null);
    try {
      setFcResult(await api.factcheckSearch(caseId, fcQuery));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(""); }
  }

  return (
    <div className="scroll" style={{ padding: 14, height: "100%", overflow: "auto", maxWidth: 900 }}>
      <h3>Live connectors</h3>
      <p className="muted">
        Sab connectors optional hain. Key configured hone par hi live calls hoti hain; warna UI honestly
        &quot;not configured&quot; dikhata hai — koi fabricated evidence nahi. Keys sirf server-side <code>.env</code> me
        rakhi jaati hain, browser kabhi unhe touch nahi karta.
      </p>

      <div style={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 8, padding: 14, margin: "14px 0" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 20 }}>⚡</span>
          <div>
            <h4 style={{ margin: 0 }}>Model Context Protocol (MCP) Mode</h4>
            <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Direct AI Agent Tool Calling (Replaces Proprietary External APIs with zero keys)
            </div>
          </div>
          <span className="badge fact" style={{ marginLeft: "auto" }}>Native MCP Active</span>
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
          Instead of configuring commercial API keys (YouTube, Gemini, FactCheck), you can connect Scamurai directly to any AI Agent (Antigravity, Claude Desktop, Cursor) via MCP:
        </p>
        <pre style={{ background: "#09090b", padding: 10, borderRadius: 6, fontSize: 12, overflowX: "auto" }}>
{`# Run Scamurai as an MCP Server:
python backend/scamurai_mcp.py

# Available MCP Tools:
• scamurai_analyze_media(image_path)      -> DCT pHash + EXIF GPS extraction
• scamurai_analyze_comments(comments)     -> Multilingual Hindi/Hinglish NLP
• scamurai_detect_coordination(posts)     -> Multi-account temporal clustering
• scamurai_extract_claims(text)           -> Fact-check query propositioning`}
        </pre>
      </div>

      <h4>Provider status</h4>
      <table>
        <thead><tr><th>Provider</th><th>Status</th><th>Detail</th></tr></thead>
        <tbody>
          {caps.map((c) => (
            <tr key={c.provider}>
              <td><b>{c.provider}</b></td>
              <td><span className={`badge ${c.configured ? "fact" : "warn"}`}>{c.status}</span></td>
              <td className="muted" style={{ fontSize: 12 }}>{c.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4 style={{ marginTop: 22 }}>YouTube comments import (Data API v3, free key)</h4>
      {!canRun && <p className="badge err">Your role ({role}) cannot run imports.</p>}
      {cap("youtube") && !cap("youtube")!.configured && (
        <p className="badge warn">SCAMURAI_YOUTUBE_API_KEY set nahi hai — server .env me key daalo, phir ye section live ho jayega.</p>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={ytUrl} onChange={(e) => setYtUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=… ya 11-char video id"
          style={{ flex: 1 }}
          disabled={!canRun || busy !== ""}
        />
        <button className="btn secondary" disabled={!canRun || busy !== "" || ytUrl.trim().length < 11}
          onClick={importYoutube}>
          {busy === "yt" ? "Importing…" : "Import comments"}
        </button>
      </div>
      {ytResult && (
        <div className="evidence-chain" style={{ marginTop: 8 }}>
          <div>Video <b>{ytResult.video_id}</b>: {ytResult.comments_created} naye comments,
            {" "}{ytResult.uncertain_duplicates_held} uncertain duplicates hold kiye gaye.</div>
          <div className="muted" style={{ fontSize: 12 }}>Coverage: {ytResult.coverage.status}</div>
        </div>
      )}

      <h4 style={{ marginTop: 22 }}>Google Fact Check search (free Claim Search API)</h4>
      {cap("factcheck") && !cap("factcheck")!.configured && (
        <p className="badge warn">SCAMURAI_GOOGLE_FACTCHECK_API_KEY set nahi hai.</p>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={fcQuery} onChange={(e) => setFcQuery(e.target.value)}
          placeholder="Claim text jise verify karna hai…"
          style={{ flex: 1 }}
          disabled={!canRun || busy !== ""}
        />
        <button className="btn secondary" disabled={!canRun || busy !== "" || fcQuery.trim().length < 3}
          onClick={factCheck}>
          {busy === "fc" ? "Searching…" : "Search fact-checks"}
        </button>
      </div>
      {fcResult && (
        <div style={{ marginTop: 8 }}>
          <p className="muted" style={{ fontSize: 12 }}>{fcResult.note}</p>
          {fcResult.matches.length === 0 && <p className="badge warn">Koi published fact-check nahi mila — ye falsity ka proof nahi hai.</p>}
          {fcResult.matches.map((m, i) => (
            <div key={i} className="evidence-chain">
              <div><b>{m.claim}</b> — <span className="badge hypothesis">{m.outcome || "unrated"}</span></div>
              <div className="muted" style={{ fontSize: 12 }}>
                {m.claimant && <>claimant: {m.claimant} · </>}{m.source}
                {m.url && <> · <a href={m.url} target="_blank" rel="noreferrer">source</a></>}
              </div>
            </div>
          ))}
        </div>
      )}

      {error && <p className="badge err" style={{ marginTop: 12 }}>{error}</p>}
    </div>
  );
}
