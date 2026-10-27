import { useCallback, useEffect, useState } from "react";
import { api, ApiError, authorizedMediaObjectUrl } from "../lib/api";
import type { Job, MediaForensicsResult } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, ErrorView, PageHeader, ScopeNotice, formatDate } from "./AnalyticsPrimitives";

export default function MediaView({ caseId, role, jobs, onChanged }: { caseId: string; role: string; jobs: Job[]; onChanged: () => void }) {
  const [rows, setRows] = useState<MediaForensicsResult[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const canRun = ["owner", "analyst"].includes(role);
  const load = useCallback(async () => {
    try { const result = await api.mediaForensics(caseId); setRows(result); if (!result.some((r) => r.id === selectedId)) setSelectedId(result[0]?.id || null); }
    catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
  }, [caseId, selectedId]);
  useEffect(() => { load(); }, [caseId]); // eslint-disable-line react-hooks/exhaustive-deps
  const mediaJob = jobs.find((job) => job.kind === "media_forensics");
  useEffect(() => { if (mediaJob?.lifecycle === "completed") load(); }, [mediaJob?.lifecycle]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run() {
    setBusy(true); setError(""); setMessage("");
    try { await api.run(caseId, "media_forensics", `media-forensics-${Date.now()}`); setMessage("Media forensics job queued. Results will appear after the worker finishes."); onChanged(); }
    catch (e) { setError(e instanceof ApiError ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const selected = rows.find((row) => row.id === selectedId) || null;
  return <div className="view-page">
    <PageHeader eyebrow="MULTIMEDIA VERIFICATION" title="Media forensics lab" description="Integrity, metadata, provenance markers and pixel residuals—plus optional configured model output." actions={<><button className="btn btn-secondary" onClick={load}><Icon name="refresh" /> Refresh</button><button className="btn btn-primary" disabled={!canRun || busy} onClick={run}>{busy ? <span className="spinner" /> : <Icon name="play" />} Run media forensics</button></>} />
    <ScopeNotice><b>No deterministic pixel statistic is a deepfake verdict.</b> Compression, resizing, cropping and camera processing can change residuals. Missing metadata or C2PA markers does not prove synthetic origin.</ScopeNotice>
    {error && <ErrorView message={error} retry={load} />}{message && <div className="inline-alert success"><Icon name="check" />{message}</div>}
    {mediaJob && ["queued", "running"].includes(mediaJob.lifecycle) && <div className="collection-progress"><span className="spinner dark" /><div><b>Media analysis {mediaJob.lifecycle}</b><p>Stage: {mediaJob.stage}</p></div></div>}
    {!rows.length ? <EmptyView icon="media" title="No media-screening results" text="Upload an authorized image from Collect data, then run media forensics. Video/deepfake analysis is not simulated when no suitable model exists." action={canRun && <button className="btn btn-primary" onClick={run}><Icon name="play" /> Run media forensics</button>} /> : <div className="media-layout">
      <aside className="media-list">{rows.map((row) => <button key={row.id} className={selectedId === row.id ? "active" : ""} onClick={() => setSelectedId(row.id)}><MediaThumb caseId={caseId} mediaId={row.media_asset_id} filename={row.filename} /><span><b>{row.filename}</b><small>{row.width}×{row.height} · {row.mime_type}</small><small>{formatDate(row.created_at)}</small></span></button>)}</aside>
      {selected && <main className="media-detail"><div className="detail-title"><div><span className="eyebrow">{selected.status.replaceAll("_", " ")}</span><h2>{selected.filename}</h2></div><span className="mini-tag">{selected.mime_type}</span></div>
        <div className="media-hero"><MediaThumb caseId={caseId} mediaId={selected.media_asset_id} filename={selected.filename} large /><div className="integrity-panel"><span className="eyebrow">FILE INTEGRITY</span><div><span>SHA-256</span><code>{selected.sha256}</code></div><div><span>DCT pHash</span><code>{selected.phash || "—"}</code></div><div><span>Dimensions</span><b>{selected.width} × {selected.height}</b></div><small>Hashes support identity and near-duplicate analysis, not caption truth or first-uploader attribution.</small></div></div>
        <ModelPanel result={selected.model_result} />
        <div className="two-column-detail"><section className="card inner"><div className="card-head"><h3>Metadata observations</h3></div><MetadataTable metadata={selected.indicators.metadata || {}} />{(selected.indicators.metadata_declarations || []).length > 0 && <div className="declaration-list">{selected.indicators.metadata_declarations.map((item: any, index: number) => <div key={index}><Icon name="info" /><span><b>{item.indicator.replaceAll("_", " ")}</b><small>{item.meaning}</small></span></div>)}</div>}</section><section className="card inner"><div className="card-head"><h3>Pixel & compression indicators</h3></div><PixelPanel pixels={selected.indicators.pixels || {}} /></section></div>
        <details className="methodology-note" open><summary><Icon name="alert" /> Forensic limitations</summary><ul>{selected.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
        <details className="methodology-note"><summary><Icon name="file" /> Raw result JSON</summary><pre className="raw-json">{JSON.stringify(selected.indicators, null, 2)}</pre></details>
      </main>}
    </div>}
  </div>;
}

function MediaThumb({ caseId, mediaId, filename, large = false }: { caseId: string; mediaId: string; filename: string; large?: boolean }) {
  const [url, setUrl] = useState("");
  useEffect(() => { let active = true; let objectUrl = ""; authorizedMediaObjectUrl(caseId, mediaId).then((value) => { if (active) { objectUrl = value; setUrl(value); } else if (value) URL.revokeObjectURL(value); }).catch(() => setUrl("")); return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); }; }, [caseId, mediaId]);
  if (!url) return <span className={`media-placeholder ${large ? "large" : ""}`}><Icon name="media" size={large ? 42 : 20} />{large && <small>Preview unavailable</small>}</span>;
  return <img className={large ? "media-preview-large" : "media-preview-thumb"} src={url} alt={filename} />;
}

function ModelPanel({ result }: { result: Record<string, any> }) {
  const score = result.synthetic_score;
  return <section className={`model-panel ${result.status}`}><div className="model-panel-title"><span className="icon-tile"><Icon name="shield" /></span><div><span className="eyebrow">SYNTHETIC-MEDIA MODEL</span><h3>{result.status === "successful" ? "Raw classifier output" : "Model score unavailable"}</h3></div><span className="source-status limited"><span />{String(result.status).replaceAll("_", " ")}</span></div>{score !== null && score !== undefined ? <div className="model-score"><strong>{(Number(score) * 100).toFixed(1)}%</strong><span>raw synthetic-label score</span><div className="meter-track"><div style={{ width: `${Number(score) * 100}%` }} /></div><small>Not calibrated operational confidence. Model: {result.model_id}</small></div> : <p>{result.detail || "No synthetic score was returned."}</p>}{Array.isArray(result.labels) && <div className="feature-tags">{result.labels.map((row: any, index: number) => <span key={index}>{row.label}: {(Number(row.score) * 100).toFixed(1)}%</span>)}</div>}{result.score_semantics && <small>{result.score_semantics}</small>}</section>;
}

function MetadataTable({ metadata }: { metadata: Record<string, unknown> }) {
  const entries = Object.entries(metadata || {});
  if (!entries.length) return <div className="empty-inline"><Icon name="info" />No selected metadata fields observed. Absence is not evidence of manipulation.</div>;
  return <div className="metadata-list">{entries.map(([key, value]) => <div key={key}><span>{key}</span><code>{String(value)}</code></div>)}</div>;
}

function PixelPanel({ pixels }: { pixels: Record<string, any> }) {
  const residual = pixels.residual_statistics || {};
  const jpeg = pixels.jpeg_recompression || {};
  const ela = pixels.ela_analysis || {};
  const fft = pixels.fft_spectral_analysis || {};
  return (
    <div className="pixel-panel">
      <div className="case-meta">
        <span>Analysed {Array.isArray(pixels.analyzed_dimensions) ? pixels.analyzed_dimensions.join("×") : "—"}</span>
        {pixels.downsampled_for_analysis && <span>Downsampled</span>}
      </div>
      <h4>Gaussian residual</h4>
      <div className="metric-pairs">
        <div><span>Mean absolute</span><b>{residual.mean_absolute ?? "—"}</b></div>
        <div><span>Std deviation</span><b>{residual.standard_deviation ?? "—"}</b></div>
        <div><span>95th percentile</span><b>{residual.p95_absolute ?? "—"}</b></div>
      </div>
      {ela.mean_error !== undefined && (
        <>
          <h4>InVID-style Error Level Analysis (ELA q95)</h4>
          <div className="metric-pairs">
            <div><span>Mean ELA error</span><b>{ela.mean_error}</b></div>
            <div><span>Max divergence</span><b>{ela.max_error}</b></div>
            <div><span>High error pixels (&gt;15)</span><b>{ela.high_error_pixel_ratio}</b></div>
          </div>
        </>
      )}
      {fft.high_frequency_energy_ratio !== undefined && (
        <>
          <h4>Sentinel-style 2D FFT Spectral Distribution</h4>
          <div className="metric-pairs">
            <div><span>High-freq energy ratio</span><b>{fft.high_frequency_energy_ratio}</b></div>
            <div><span>Low-freq energy ratio</span><b>{fft.low_frequency_energy_ratio}</b></div>
            <div><span>Spectral balance</span><b>{fft.spectral_energy_balance}</b></div>
          </div>
        </>
      )}
      <h4>JPEG q90 re-compression</h4>
      {jpeg.status === "not_applicable" ? (
        <p className="muted">{jpeg.reason || "Not applicable to this file type."}</p>
      ) : (
        <div className="metric-pairs">
          <div><span>Mean difference</span><b>{jpeg.mean_absolute_channel_difference ?? "—"}</b></div>
          <div><span>95th percentile</span><b>{jpeg.p95_absolute_channel_difference ?? "—"}</b></div>
          <div><span>Differences &gt; 20</span><b>{jpeg.fraction_channel_differences_above_20 ?? "—"}</b></div>
        </div>
      )}
      <small>Measurements are provided for comparison and review; no universal manipulation threshold is applied.</small>
    </div>
  );
}
