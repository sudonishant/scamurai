import { useMemo } from "react";
import { geoNaturalEarth1, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import worldAtlas from "world-atlas/countries-110m.json";
import type { AnalyticsData } from "../lib/types";
import Icon from "./Icon";
import { EmptyView, MetricCard, PageHeader, ScopeNotice, formatDate } from "./AnalyticsPrimitives";

function suppliedCount(value: unknown): number | undefined {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : undefined;
}

function countLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function sumSuppliedCounts(rows: Record<string, any>[], field: string): number | undefined {
  const counts = rows.map((row) => suppliedCount(row[field]));
  if (counts.some((count) => count === undefined)) return undefined;
  return (counts as number[]).reduce((sum, count) => sum + count, 0);
}

function SuppressionNotice({ data }: { data: AnalyticsData }) {
  const privacy = data.geospatial.privacy;
  const groups = suppliedCount(privacy?.suppressed_groups);
  const observations = suppliedCount(privacy?.suppressed_observations);
  const minimum = suppliedCount(privacy?.minimum_group_size);
  const hasSuppression = (groups ?? 0) > 0 || (observations ?? 0) > 0;
  if (!hasSuppression) return null;

  const details = [
    minimum === undefined ? null : `Minimum group size is ${minimum} distinct observed subjects.`,
    groups === undefined || groups === 0 ? null : `${countLabel(groups, "group")} withheld.`,
    observations === undefined || observations === 0 ? null : `${countLabel(observations, "observation")} withheld.`,
  ].filter(Boolean).join(" ");

  return <ScopeNotice tone="warning">
    <b>Some location aggregates are withheld by the privacy threshold.</b> {details} Withheld location names and coordinates are not displayed. Suppression is not evidence of absence.
  </ScopeNotice>;
}

function GeoEmptyState({ data }: { data: AnalyticsData }) {
  const privacy = data.geospatial.privacy;
  const groups = suppliedCount(privacy?.suppressed_groups);
  const observations = suppliedCount(privacy?.suppressed_observations);
  const geoPosts = suppliedCount(data.coverage?.geolocated_posts);
  const privacyCountsComplete = groups !== undefined && observations !== undefined;
  const hasSuppression = (groups ?? 0) > 0 || (observations ?? 0) > 0;

  if (hasSuppression) {
    return <>
      <SuppressionNotice data={data} />
      <EmptyView icon="map" title="Locations withheld by privacy threshold" text="The API reports privacy-threshold suppression, but returns no displayable aggregates. Suppressed locations remain unnamed and unmapped; their absence from this view does not mean they were not observed." />
    </>;
  }

  if (geoPosts === 0 && privacyCountsComplete && groups === 0 && observations === 0) {
    return <EmptyView icon="map" title="No geo observations reported" text="The API reports 0 linked posts with geospatial observations in this case’s collected corpus. This does not establish whether locations exist outside the collected case data." />;
  }

  if (geoPosts !== undefined && geoPosts > 0) {
    return <EmptyView icon="map" title="No displayable location aggregates" text={`The API reports ${countLabel(geoPosts, "linked post")} with geospatial observations, but returned no displayable aggregate. The response does not establish why; review source coverage before drawing conclusions.`} />;
  }

  return <EmptyView icon="map" title="Geospatial status unavailable" text="This analytics response does not include enough coverage and privacy counts to distinguish no observations from threshold suppression. No location or count has been inferred." />;
}

export default function GeoView({ data, onRefresh }: { data: AnalyticsData | null; onRefresh: () => void }) {
  if (!data) return <div className="view-page"><PageHeader eyebrow="GEOSPATIAL ANALYTICS" title="Location patterns" description="Aggregated source-reported observations with baseline rules." /><EmptyView icon="map" title="No analytics yet" text="Collect an authorized corpus, then refresh. Missing location is never invented." /></div>;

  const points = data.geospatial.points || [];
  const locations = data.geospatial.locations || [];
  const anomalies = data.geospatial.anomalies || [];
  const hasDisplayableAggregates = locations.length > 0 || points.length > 0;
  const geoPosts = suppliedCount(data.coverage?.geolocated_posts);
  const visibleObservationCount = sumSuppliedCounts(locations, "observation_count");
  const minimumGroupSize = suppliedCount(data.geospatial.privacy?.minimum_group_size);

  if (!hasDisplayableAggregates) return <div className="view-page">
    <PageHeader eyebrow="GEOSPATIAL ANALYTICS" title="Location patterns" description="Aggregated source-reported observations with baseline rules." />
    <GeoEmptyState data={data} />
  </div>;

  return <div className="view-page">
    <PageHeader eyebrow="GEOSPATIAL ANALYTICS" title="Location patterns" description="Compare observed narrative volume across source-reported places and time buckets." actions={<button className="btn btn-secondary" onClick={onRefresh}><Icon name="refresh" /> Recompute</button>} />
    <SuppressionNotice data={data} />
    <ScopeNotice><b>Heat points are not live locations.</b> {data.geospatial.map_note} A spike may reflect collection changes, a real local event or a coordinated campaign; the map alone cannot distinguish them.</ScopeNotice>
    <div className="metric-grid four">
      <MetricCard label="Observed locations" value={locations.length} note={minimumGroupSize === undefined ? "Returned aggregate records" : `k ≥ ${minimumGroupSize} distinct subjects`} icon="map" />
      <MetricCard label="Displayed geo observations" value={visibleObservationCount ?? "—"} note={geoPosts === undefined ? "Linked-post count not provided" : `${geoPosts} linked posts reported`} icon="layers" />
      <MetricCard label="Mapped aggregates" value={points.length} note="Returned aggregate coordinates only" icon="globe" />
      <MetricCard label="Baseline spikes" value={anomalies.length} note="Review cues, not attribution" icon="alert" tone={anomalies.length ? "warning" : "default"} />
    </div>
    <section className="card map-card"><div className="card-head"><div><span className="eyebrow">AGGREGATED HEAT MAP</span><h2>Observed narrative locations</h2></div><div className="map-legend"><span><i className="normal" />Observed</span><span><i className="anomaly" />Baseline spike</span></div></div><GeoMap points={points} /><div className="map-caption">Offline Natural Earth country boundaries · circle size represents collected observation count, not population or harm.</div></section>
    <section className="card"><div className="card-head"><div><span className="eyebrow">BASELINE REVIEW</span><h2>Location timelines & anomalies</h2></div></div><div className="table-wrap"><table className="data-table"><thead><tr><th>Location</th><th>Observations</th><th>Source & precision</th><th>Last observed</th><th>Baseline</th><th>Assessment</th></tr></thead><tbody>{locations.map((location) => <tr key={String(location.key)}><td><b>{String(location.label)}</b><small>{Array.isArray(location.narrative_ids) ? `${location.narrative_ids.length} linked narratives` : ""}</small></td><td>{suppliedCount(location.observation_count) ?? "—"}<small>{suppliedCount(location.post_count) === undefined ? "—" : `${location.post_count} posts`} · {suppliedCount(location.protected_subject_count) === undefined ? "—" : `${location.protected_subject_count} subjects`}</small></td><td><span>{Array.isArray(location.sources) ? location.sources.join(", ") : "unknown"}</span><small>{Array.isArray(location.precisions) ? location.precisions.join(", ") : "unknown"}</small></td><td>{formatDate(location.last_observed)}</td><td><span className={`status-badge ${location.baseline_status === "available" ? "available" : "insufficient"}`}>{String(location.baseline_status || "unknown").replaceAll("_", " ")}</span></td><td>{location.anomaly ? <span className="review-chip"><Icon name="alert" size={13} /> Review spike</span> : <span className="muted">No rule crossed</span>}</td></tr>)}</tbody></table></div></section>
    {anomalies.length > 0 && <section className="card"><div className="card-head"><div><span className="eyebrow">EXPLAINABLE RULES</span><h2>Why a spike was flagged</h2></div></div><div className="anomaly-grid">{anomalies.map((anomaly, index) => <div className="anomaly-card" key={index}><Icon name="alert" /><div><b>{String(anomaly.location)}</b><p>Latest {String(anomaly.latest_count)} · baseline mean {String(anomaly.baseline_mean)} · σ {String(anomaly.baseline_stddev)}</p><code>{String(anomaly.rule)}</code><small>Inspect source coverage and benign explanations before action.</small></div></div>)}</div></section>}
  </div>;
}

function GeoMap({ points }: { points: AnalyticsData["geospatial"]["points"] }) {
  const map = useMemo(() => {
    const countries = feature(worldAtlas as any, (worldAtlas as any).objects.countries) as any;
    const projection = geoNaturalEarth1().fitSize([960, 440], countries);
    const path = geoPath(projection);
    return { countries, projection, path, countryPath: path(countries) || "" };
  }, []);
  return <div className="geo-map"><svg viewBox="0 0 960 440" role="img" aria-label="World map with aggregated observation points"><path d={map.countryPath} className="world-shape" />{points.map((point) => { const xy = map.projection([point.longitude, point.latitude]); if (!xy) return null; const count = suppliedCount(point.count); if (count === undefined) return null; const radius = 5 + Math.sqrt(count) * 2.2; return <g key={point.key} className={point.anomaly ? "heat-point anomaly" : "heat-point"} transform={`translate(${xy[0]},${xy[1]})`}><circle r={radius + 5} className="heat-halo" /><circle r={radius} className="heat-core" /><text y={-radius - 9} textAnchor="middle">{point.label} · {count}</text><title>{point.label}: {count} observations{point.anomaly ? " — baseline spike" : ""}</title></g>; })}</svg></div>;
}
