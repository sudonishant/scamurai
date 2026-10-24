import { useMemo } from "react";
import { geoNaturalEarth1, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import worldAtlas from "world-atlas/countries-110m.json";
import type { AnalyticsData } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, MetricCard, PageHeader, ScopeNotice, formatDate } from "./AnalyticsPrimitives";

export default function GeoView({ data, onRefresh }: { data: AnalyticsData | null; onRefresh: () => void }) {
  const points = data?.geospatial.points || [];
  const locations = data?.geospatial.locations || [];
  if (!data || !locations.length) return <div className="view-page"><PageHeader eyebrow="GEOSPATIAL ANALYTICS" title="Location patterns" description="Aggregated source-reported observations with baseline rules." /><EmptyView icon="map" title="No usable location observations" text="Import post location fields or run photo-to-location on media with EXIF GPS. Missing location is never invented." /></div>;
  return <div className="view-page">
    <PageHeader eyebrow="GEOSPATIAL ANALYTICS" title="Location patterns" description="Compare observed narrative volume across source-reported places and time buckets." actions={<button className="btn btn-secondary" onClick={onRefresh}><Icon name="refresh" /> Recompute</button>} />
    <ScopeNotice><b>Heat points are not live locations.</b> {data.geospatial.map_note} A spike may reflect collection changes, a real local event or a coordinated campaign; the map alone cannot distinguish them.</ScopeNotice>
    <div className="metric-grid four"><MetricCard label="Observed locations" value={locations.length} note="Named or coordinate groups" icon="map" /><MetricCard label="Geo observations" value={locations.reduce((sum, row) => sum + Number(row.observation_count || 0), 0)} note={`${Number(data.coverage.geolocated_posts || 0)} linked posts`} icon="layers" /><MetricCard label="Mapped aggregates" value={points.length} note="Coordinates rounded to 2 decimals" icon="globe" /><MetricCard label="Baseline spikes" value={data.geospatial.anomalies.length} note="Review cues, not attribution" icon="alert" tone={data.geospatial.anomalies.length ? "warning" : "default"} /></div>
    <section className="card map-card"><div className="card-head"><div><span className="eyebrow">AGGREGATED HEAT MAP</span><h2>Observed narrative locations</h2></div><div className="map-legend"><span><i className="normal" />Observed</span><span><i className="anomaly" />Baseline spike</span></div></div><GeoMap data={data} /><div className="map-caption">Offline Natural Earth country boundaries · circle size represents collected observation count, not population or harm.</div></section>
    <section className="card"><div className="card-head"><div><span className="eyebrow">BASELINE REVIEW</span><h2>Location timelines & anomalies</h2></div></div><div className="table-wrap"><table className="data-table"><thead><tr><th>Location</th><th>Observations</th><th>Source & precision</th><th>Last observed</th><th>Baseline</th><th>Assessment</th></tr></thead><tbody>{locations.map((location) => <tr key={String(location.key)}><td><b>{String(location.label)}</b><small>{Array.isArray(location.narrative_ids) ? `${location.narrative_ids.length} linked narratives` : ""}</small></td><td>{String(location.observation_count)}<small>{String(location.post_count)} posts</small></td><td><span>{Array.isArray(location.sources) ? location.sources.join(", ") : "unknown"}</span><small>{Array.isArray(location.precisions) ? location.precisions.join(", ") : "unknown"}</small></td><td>{formatDate(location.last_observed)}</td><td><span className={`status-badge ${location.baseline_status === "available" ? "available" : "insufficient"}`}>{String(location.baseline_status).replaceAll("_", " ")}</span></td><td>{location.anomaly ? <span className="review-chip"><Icon name="alert" size={13} /> Review spike</span> : <span className="muted">No rule crossed</span>}</td></tr>)}</tbody></table></div></section>
    {data.geospatial.anomalies.length > 0 && <section className="card"><div className="card-head"><div><span className="eyebrow">EXPLAINABLE RULES</span><h2>Why a spike was flagged</h2></div></div><div className="anomaly-grid">{data.geospatial.anomalies.map((anomaly, index) => <div className="anomaly-card" key={index}><Icon name="alert" /><div><b>{String(anomaly.location)}</b><p>Latest {String(anomaly.latest_count)} · baseline mean {String(anomaly.baseline_mean)} · σ {String(anomaly.baseline_stddev)}</p><code>{String(anomaly.rule)}</code><small>Inspect source coverage and benign explanations before action.</small></div></div>)}</div></section>}
  </div>;
}

function GeoMap({ data }: { data: AnalyticsData }) {
  const map = useMemo(() => {
    const countries = feature(worldAtlas as any, (worldAtlas as any).objects.countries) as any;
    const projection = geoNaturalEarth1().fitSize([960, 440], countries);
    const path = geoPath(projection);
    return { countries, projection, path, countryPath: path(countries) || "" };
  }, []);
  return <div className="geo-map"><svg viewBox="0 0 960 440" role="img" aria-label="World map with aggregated observation points"><path d={map.countryPath} className="world-shape" />{data.geospatial.points.map((point) => { const xy = map.projection([point.longitude, point.latitude]); if (!xy) return null; const radius = 5 + Math.sqrt(point.count) * 2.2; return <g key={point.key} className={point.anomaly ? "heat-point anomaly" : "heat-point"} transform={`translate(${xy[0]},${xy[1]})`}><circle r={radius + 5} className="heat-halo" /><circle r={radius} className="heat-core" /><text y={-radius - 9} textAnchor="middle">{point.label} · {point.count}</text><title>{point.label}: {point.count} observations{point.anomaly ? " — baseline spike" : ""}</title></g>; })}</svg></div>;
}
