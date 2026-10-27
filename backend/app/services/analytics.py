"""Explainable narrative, behavior, network, geospatial and warning analytics.

All calculations are scoped to the collected case corpus. The service does not
claim platform-wide origin, influence, account ownership, bot probability or a
binary organic/orchestrated verdict. Numeric values are transparent screening
metrics with evidence coverage, never calibrated probabilities.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from urllib.parse import urlparse

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    Account,
    CoordinationCandidate,
    GeoObservation,
    GraphEdge,
    GraphNode,
    MediaAsset,
    Post,
    SourceAccess,
    utcnow,
)
from .alerts import sync_alerts

settings = get_settings()

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were", "has", "have", "had",
    "you", "your", "yours", "our", "out", "all", "not", "but", "who", "what", "when", "where", "why", "how",
    "will", "would", "can", "could", "should", "there", "their", "they", "them", "then", "than", "into", "about",
    "just", "now", "new", "more", "very", "been", "being", "over", "under", "after", "before", "via", "amp",
    "aaj", "aur", "ka", "ki", "ke", "ko", "se", "me", "mein", "hai", "hain", "ho", "hota", "hoti", "hote",
    "ye", "yeh", "wo", "woh", "kya", "kaa", "eka", "par", "per", "bhi", "hi", "nahi", "nahin", "kiya", "kiye",
    "की", "का", "के", "को", "से", "में", "है", "हैं", "और", "या", "पर", "भी", "नहीं", "यह", "वह", "इस", "उस",
}
MAX_CLUSTER_POSTS = 500


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _tokens(text: str) -> list[str]:
    """Unicode-aware tokens that retain combining marks inside words."""
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    tokens: list[str] = []
    current: list[str] = []
    for char in normalized:
        if char.isalnum() or unicodedata.category(char).startswith("M"):
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return [token for token in tokens
            if len(token) >= 3 and token not in STOPWORDS and not token.isnumeric()]


def _bucket_size(start: datetime | None, end: datetime | None) -> str:
    if not start or not end:
        return "day"
    span = end - start
    if span <= timedelta(hours=48):
        return "hour"
    if span <= timedelta(days=180):
        return "day"
    return "week"


def _bucket_start(value: datetime, size: str) -> datetime:
    value = _dt(value) or value
    if size == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if size == "week":
        day = value - timedelta(days=value.weekday())
        return day.replace(hour=0, minute=0, second=0, microsecond=0)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _next_bucket(value: datetime, size: str) -> datetime:
    return value + (timedelta(hours=1) if size == "hour" else timedelta(days=7) if size == "week" else timedelta(days=1))


def _timeline(items: Iterable[tuple[datetime | None, str]], span_start: datetime | None = None,
              span_end: datetime | None = None) -> tuple[str, list[dict], int]:
    dated = [(d, item_id) for d, item_id in items if d]
    undated = sum(1 for d, _ in items if not d)
    if not dated:
        return "day", [], undated
    start = min([d for d, _ in dated] + ([span_start] if span_start else []))
    end = max([d for d, _ in dated] + ([span_end] if span_end else []))
    size = _bucket_size(start, end)
    counts: dict[datetime, int] = Counter()
    ids: dict[datetime, list[str]] = defaultdict(list)
    for value, item_id in dated:
        bucket = _bucket_start(value, size)
        counts[bucket] += 1
        if len(ids[bucket]) < 30:
            ids[bucket].append(item_id)
    first, last = min(counts), max(counts)
    rows = []
    cursor = first
    # Avoid enormous timeline responses for poorly timestamped imports.
    while cursor <= last and len(rows) < 200:
        rows.append({"bucket": _iso(cursor), "count": counts.get(cursor, 0), "evidence_ids": ids.get(cursor, [])})
        cursor = _next_bucket(cursor, size)
    if cursor <= last:
        rows.append({"bucket": _iso(last), "count": counts[last], "evidence_ids": ids[last], "truncated_before": True})
    return size, rows, undated


class _UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, a: int, b: int):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.parent[b] = a


def _tfidf_vectors(posts: list[Post]) -> tuple[list[dict[str, float]], list[set[str]]]:
    token_rows = [_tokens(p.normalized_text or p.raw_text) for p in posts]
    df: Counter[str] = Counter()
    for row in token_rows:
        df.update(set(row))
    n = max(len(posts), 1)
    vectors = []
    for row in token_rows:
        counts = Counter(row)
        raw = {term: count * (math.log((n + 1) / (df[term] + 1)) + 1) for term, count in counts.items()}
        norm = math.sqrt(sum(value * value for value in raw.values())) or 1.0
        vectors.append({term: value / norm for term, value in raw.items()})
    return vectors, [set(row) for row in token_rows]


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(term, 0.0) for term, value in a.items())


def _cluster_posts(posts: list[Post]) -> list[list[Post]]:
    if not posts:
        return []
    vectors, token_sets = _tfidf_vectors(posts)
    uf = _UnionFind(len(posts))
    for i in range(len(posts)):
        if not token_sets[i]:
            continue
        for j in range(i + 1, len(posts)):
            if not token_sets[j]:
                continue
            exact = bool(posts[i].normalized_text and posts[i].normalized_text == posts[j].normalized_text)
            if exact or _cosine(vectors[i], vectors[j]) >= 0.48:
                uf.union(i, j)
    groups: dict[int, list[Post]] = defaultdict(list)
    for index, post in enumerate(posts):
        groups[uf.find(index)].append(post)
    return list(groups.values())


def _acceleration(timeline: list[dict], account_count: int, evidence_ids: list[str]) -> dict | None:
    if len(timeline) < 4:
        return None
    latest = int(timeline[-1]["count"])
    baseline = [int(row["count"]) for row in timeline[-4:-1]]
    mean = statistics.fmean(baseline)
    if latest < 3 or account_count < 2 or latest < max(2, 2 * max(mean, 0.25)):
        return None
    acceleration = (latest - mean) / max(mean, 1.0)
    score = min(100, round(50 * min(acceleration / 3, 1) + 30 * min(latest / 10, 1) + 20 * min(account_count / 5, 1)))
    return {
        "attention_score": score,
        "score_type": "transparent_rule_score_not_probability",
        "severity": "high" if score >= 75 else "elevated" if score >= 55 else "review",
        "latest_count": latest,
        "baseline_counts": baseline,
        "baseline_mean": round(mean, 3),
        "acceleration_ratio": round(acceleration, 3),
        "evidence_ids": evidence_ids[:50],
        "rule": "latest>=3; accounts>=2; latest>=2*max(baseline_mean,0.25); baseline=previous 3 buckets",
    }


def _build_narratives(posts: list[Post], accounts: dict[str, Account], truncated: bool) -> tuple[list[dict], dict[str, str]]:
    clusters = _cluster_posts(posts)
    narratives = []
    post_to_narrative: dict[str, str] = {}
    for cluster in clusters:
        cluster = sorted(cluster, key=lambda p: _dt(p.timestamp) or _dt(p.created_at) or datetime.min.replace(tzinfo=UTC))
        post_ids = [p.id for p in cluster]
        digest = hashlib.sha256(",".join(sorted(post_ids)).encode()).hexdigest()[:12]
        narrative_id = f"narrative-{digest}"
        for post_id in post_ids:
            post_to_narrative[post_id] = narrative_id
        term_counts: Counter[str] = Counter()
        for post in cluster:
            term_counts.update(_tokens(post.normalized_text or post.raw_text))
        top_terms = [{"term": term, "count": count} for term, count in term_counts.most_common(8)]
        label = " · ".join(row["term"] for row in top_terms[:3]) or (cluster[0].raw_text[:80] or "Untexted narrative")
        account_ids = sorted({p.account_id for p in cluster if p.account_id})
        dated = [_dt(p.timestamp) for p in cluster if p.timestamp]
        size, timeline, undated = _timeline([(p.timestamp, p.id) for p in cluster])
        by_account: dict[str, list[Post]] = defaultdict(list)
        for post in cluster:
            if post.account_id:
                by_account[post.account_id].append(post)
        propagation = []
        for account_id, account_posts in sorted(by_account.items(), key=lambda item: min(
                [_dt(p.timestamp) or datetime.max.replace(tzinfo=UTC) for p in item[1]])):
            first = account_posts[0]
            propagation.append({
                "account_id": account_id,
                "handle": accounts[account_id].handle if account_id in accounts else "unknown",
                "first_observed": _iso(first.timestamp),
                "source_timestamp": _iso(first.timestamp),
                "first_seen_at": _iso(first.first_seen_at or first.created_at),
                "post_id": first.id,
                "role": "earliest_observed" if not propagation else "later_observed_amplification",
            })
        first_dated = next((p for p in cluster if p.timestamp), None)
        alert = _acceleration(timeline, len(account_ids), post_ids)
        narratives.append({
            "id": narrative_id,
            "label": label[:240],
            "post_count": len(cluster),
            "account_count": len(account_ids),
            "account_ids": account_ids,
            "evidence_post_ids": post_ids,
            "first_observed": _iso(min(dated)) if dated else None,
            "last_observed": _iso(max(dated)) if dated else None,
            "undated_posts": undated,
            "top_terms": top_terms,
            "bucket_size": size,
            "timeline": timeline,
            "earliest_observed": ({
                "post_id": first_dated.id,
                "account_id": first_dated.account_id,
                "handle": accounts[first_dated.account_id].handle if first_dated.account_id in accounts else "unknown",
                "url": first_dated.canonical_url,
                "observed_at": _iso(first_dated.timestamp),
                "source_timestamp": _iso(first_dated.timestamp),
                "first_seen_at": _iso(first_dated.first_seen_at or first_dated.created_at),
                "collected_at": _iso(first_dated.collected_at or first_dated.created_at),
                "scope": "Earliest source timestamp in this collected corpus, not proof of platform-wide origin; collection timestamps are separate.",
            } if first_dated else None),
            "propagation": propagation,
            "representative_posts": [{
                "id": p.id,
                "text": p.raw_text[:700],
                "url": p.canonical_url,
                "observed_at": _iso(p.timestamp),
                "source_timestamp": _iso(p.timestamp),
                "first_seen_at": _iso(p.first_seen_at or p.created_at),
                "collected_at": _iso(p.collected_at or p.created_at),
                "timestamp_precision": p.timestamp_precision,
                "handle": accounts[p.account_id].handle if p.account_id in accounts else "unknown",
            } for p in cluster[:5]],
            "discourse_assessment": {
                "state": "cross_account_content_similarity_observed" if len(account_ids) > 1 else "single_account_or_unlinked_observed",
                "interpretation": "Similarity and timing alone cannot distinguish organic viral discourse from an orchestrated campaign.",
            },
            "early_warning": alert,
            "locations": [],
        })
    narratives.sort(key=lambda n: (bool(n["early_warning"]), n["account_count"], n["post_count"], n["last_observed"] or ""), reverse=True)
    for narrative in narratives:
        narrative["analysis_scope"] = "TF-IDF cosine >=0.48 or exact normalized text; lexical narrative candidates require analyst review."
        if truncated:
            narrative["corpus_truncated"] = True
    return narratives[:50], post_to_narrative


def _automation_indicators(posts: list[Post], accounts: dict[str, Account]) -> list[dict]:
    by_account: dict[str, list[Post]] = defaultdict(list)
    text_accounts: dict[str, set[str]] = defaultdict(set)
    for post in posts:
        if post.account_id:
            by_account[post.account_id].append(post)
        if post.normalized_text and post.account_id:
            text_accounts[post.normalized_text].add(post.account_id)
    rows = []
    for account_id, account_posts in by_account.items():
        n = len(account_posts)
        ordered = sorted(account_posts, key=lambda p: _dt(p.timestamp) or datetime.min.replace(tzinfo=UTC))
        times = [_dt(p.timestamp) for p in ordered if p.timestamp]
        intervals = [(b - a).total_seconds() for a, b in pairwise(times) if (b - a).total_seconds() >= 0]
        normalized = [p.normalized_text for p in ordered if p.normalized_text]
        duplicate_ratio = (len(normalized) - len(set(normalized))) / n if n else 0.0
        shared_count = sum(1 for p in ordered if p.normalized_text and len(text_accounts[p.normalized_text]) > 1)
        cross_account_shared_ratio = shared_count / n if n else 0.0
        burst_ratio = (sum(value <= 60 for value in intervals) / len(intervals)) if intervals else 0.0
        if len(intervals) >= 2 and statistics.fmean(intervals) > 0:
            regularity = max(0.0, 1.0 - statistics.pstdev(intervals) / statistics.fmean(intervals))
        else:
            regularity = 0.0
        span_seconds = (max(times) - min(times)).total_seconds() if len(times) >= 2 else 0.0
        posts_per_hour = n / (span_seconds / 3600) if span_seconds >= 3600 else None
        high_rate_indicator = min((posts_per_hour or 0) / 24, 1.0) if posts_per_hour is not None else 0.0
        timestamp_coverage = len(times) / n if n else 0.0
        evidence_coverage = min(1.0, 0.5 * min(n / 20, 1) + 0.3 * timestamp_coverage + 0.2 * min(span_seconds / (7 * 86400), 1))
        score = None
        if n >= 3:
            score = round(100 * (0.30 * cross_account_shared_ratio + 0.20 * duplicate_ratio + 0.20 * burst_ratio + 0.15 * regularity + 0.15 * high_rate_indicator), 1)
        triggered = []
        if cross_account_shared_ratio >= 0.4:
            triggered.append("high_cross_account_identical_text_ratio")
        if duplicate_ratio >= 0.3:
            triggered.append("high_within_account_repetition")
        if burst_ratio >= 0.4:
            triggered.append("frequent_sub_60_second_intervals")
        if regularity >= 0.75 and len(intervals) >= 3:
            triggered.append("unusually_regular_observed_intervals")
        if high_rate_indicator >= 0.5:
            triggered.append("high_observed_posting_rate")
        rows.append({
            "account_id": account_id,
            "handle": accounts[account_id].handle if account_id in accounts else "unknown",
            "platform": accounts[account_id].platform if account_id in accounts else "unknown",
            "post_count": n,
            "automation_indicator_score": score,
            "score_type": "transparent_heuristic_not_bot_probability",
            "evidence_coverage": round(evidence_coverage, 3),
            "status": "insufficient_data" if score is None else "review_recommended" if score >= 65 and evidence_coverage >= 0.5 else "monitor",
            "features": {
                "cross_account_identical_text_ratio": round(cross_account_shared_ratio, 4),
                "within_account_duplicate_ratio": round(duplicate_ratio, 4),
                "sub_60_second_interval_ratio": round(burst_ratio, 4),
                "timing_regularity": round(regularity, 4),
                "posts_per_hour": round(posts_per_hour, 3) if posts_per_hour is not None else None,
                "observed_span_seconds": round(span_seconds, 1),
                "timestamped_posts": len(times),
            },
            "triggered_indicators": triggered,
            "formula": "100*(.30*cross_account_shared + .20*duplicates + .20*bursts + .15*regularity + .15*min(posts_per_hour/24,1))",
            "limitations": [
                "This is not a calibrated bot probability and does not establish who controls an account.",
                "Scheduling tools, newsrooms, campaigns and ordinary viral sharing can produce the same features.",
                "Only imported posts and timestamp precisions are visible; platform-wide history is not inferred.",
            ],
            "evidence_post_ids": [p.id for p in ordered[:50]],
        })
    return sorted(rows, key=lambda row: (row["automation_indicator_score"] is not None, row["automation_indicator_score"] or -1), reverse=True)


def _class_graph_metrics(output_edges: list[dict], accounts: dict[str, Account],
                         derivation_class: str) -> dict:
    selected = [edge for edge in output_edges
                if (edge["derivation_class"] == "fact") == (derivation_class == "fact")]
    graph = nx.DiGraph()
    graph.add_edges_from((edge["source_account_id"], edge["target_account_id"])
                         for edge in selected)
    empty = {"pagerank": {}, "betweenness": {}, "articulation": set(),
             "communities": [], "status": "no_edges", "betweenness_method": "not_applicable"}
    if not graph:
        return empty
    if len(graph) > 2000:
        return {**empty, "status": "skipped_graph_over_2000_nodes"}

    pagerank = nx.pagerank(graph, alpha=0.85, max_iter=100)
    undirected = graph.to_undirected()
    sampled = len(graph) > 200
    betweenness = nx.betweenness_centrality(
        undirected, k=min(100, len(graph) - 1) if sampled else None,
        normalized=True, seed=42 if sampled else None,
    )
    communities = []
    for index, community in enumerate(nx.community.louvain_communities(undirected, seed=42)):
        members = sorted(community)
        communities.append({
            "id": f"{derivation_class}-community-{index + 1}",
            "derivation_class": derivation_class,
            "account_ids": members,
            "handles": [accounts[account_id].handle for account_id in members if account_id in accounts],
            "size": len(members),
            "algorithm": "Louvain modularity, deterministic seed 42",
            "note": "Community is structural grouping within this evidence class, not common ownership or intent.",
        })
    return {
        "pagerank": pagerank,
        "betweenness": betweenness,
        "articulation": set(nx.articulation_points(undirected)),
        "communities": communities,
        "status": "computed",
        "betweenness_method": "sampled_k_max_100_seed_42" if sampled else "exact",
    }


def _build_network(db: Session, case_id: str, accounts: dict[str, Account], posts: list[Post]) -> dict:
    account_nodes = db.scalars(select(GraphNode).where(GraphNode.case_id == case_id, GraphNode.entity_type == "account")).all()
    entity_by_node = {node.id: node.entity_id for node in account_nodes}
    edges = db.scalars(select(GraphEdge).where(GraphEdge.case_id == case_id)).all()
    output_edges = []
    adjacency: dict[str, set[str]] = defaultdict(set)
    fact_degree: Counter[str] = Counter()
    hypothesis_degree: Counter[str] = Counter()
    for edge in edges:
        source = entity_by_node.get(edge.source_node_id)
        target = entity_by_node.get(edge.target_node_id)
        if not source or not target or source == target:
            continue
        if edge.relationship not in {"PUBLICLY_CROSSLINKS", "POSSIBLY_COORDINATED_WITH"}:
            continue
        output_edges.append({
            "source_account_id": source, "target_account_id": target,
            "relationship": edge.relationship, "derivation_class": edge.derivation_class,
            "statement": edge.statement, "evidence_ids": json.loads(edge.evidence_ids),
        })
        adjacency[source].add(target)
        adjacency[target].add(source)
        if edge.derivation_class == "fact":
            fact_degree[source] += 1
            fact_degree[target] += 1
        else:
            hypothesis_degree[source] += 1
            hypothesis_degree[target] += 1

    fact_metrics = _class_graph_metrics(output_edges, accounts, "fact")
    hypothesis_metrics = _class_graph_metrics(output_edges, accounts, "hypothesis")
    post_counts = Counter(p.account_id for p in posts if p.account_id)
    rows = []
    for account_id, account in accounts.items():
        bridge_classes = [name for name, metrics in (("fact", fact_metrics), ("hypothesis", hypothesis_metrics))
                          if account_id in metrics["articulation"]]
        rows.append({
            "account_id": account_id,
            "handle": account.handle,
            "platform": account.platform,
            "post_count": post_counts[account_id],
            "fact_link_degree": fact_degree[account_id],
            "hypothesis_link_degree": hypothesis_degree[account_id],
            "observed_link_degree": len(adjacency[account_id]),
            "fact_pagerank": (round(fact_metrics["pagerank"][account_id], 6)
                              if account_id in fact_metrics["pagerank"] else None),
            "fact_betweenness": (round(fact_metrics["betweenness"][account_id], 6)
                                 if account_id in fact_metrics["betweenness"] else None),
            "hypothesis_pagerank": (round(hypothesis_metrics["pagerank"][account_id], 6)
                                    if account_id in hypothesis_metrics["pagerank"] else None),
            "hypothesis_betweenness": (round(hypothesis_metrics["betweenness"][account_id], 6)
                                       if account_id in hypothesis_metrics["betweenness"] else None),
            "bridge_candidate": bool(bridge_classes),
            "bridge_evidence_classes": bridge_classes,
            "scope": "Observed case-graph position, not platform-wide influence, reach or control.",
        })
    rows.sort(key=lambda row: (row["fact_link_degree"], row["observed_link_degree"], row["post_count"]), reverse=True)

    visited: set[str] = set()
    clusters = []
    for account_id in accounts:
        if account_id in visited or not adjacency[account_id]:
            continue
        stack, component = [account_id], []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(adjacency[current] - visited)
        if len(component) > 1:
            clusters.append({
                "account_ids": sorted(component),
                "handles": [accounts[a].handle for a in component if a in accounts],
                "size": len(component),
                "fact_links": sum(1 for e in output_edges if e["derivation_class"] == "fact" and e["source_account_id"] in component and e["target_account_id"] in component),
                "hypothesis_links": sum(1 for e in output_edges if e["derivation_class"] != "fact" and e["source_account_id"] in component and e["target_account_id"] in component),
                "note": "Connected components include the displayed evidence classes; cluster membership does not prove common ownership or intent.",
            })
    clusters.sort(key=lambda row: row["size"], reverse=True)
    return {
        "nodes": rows,
        "edges": output_edges,
        "clusters": clusters,
        "communities": fact_metrics["communities"] + hypothesis_metrics["communities"],
        "metrics": {
            "centrality_scope": "PageRank and betweenness are computed separately for fact and hypothesis edge classes; they are structural screening metrics, not influence probabilities.",
            "fact_status": fact_metrics["status"],
            "hypothesis_status": hypothesis_metrics["status"],
            "fact_betweenness_method": fact_metrics["betweenness_method"],
            "hypothesis_betweenness_method": hypothesis_metrics["betweenness_method"],
            "bridge_definition": "Articulation point within the displayed fact or hypothesis graph; removing it would disconnect that observed structure.",
            "cascade_depth": {
                "status": "unavailable_no_repost_or_reply_dag",
                "reason": "Actual parent/repost edges are required; lexical clusters and timestamp order are not a cascade.",
            },
        },
        "limitations": [
            "No follower count, private connection or platform-wide reach is inferred.",
            "Fact and hypothesis links remain separately labelled, including centrality and communities.",
            "Centrality and articulation describe this bounded observed graph only; they do not establish coordination, control or audience influence.",
        ],
    }


def _build_geo(observations: list[GeoObservation], post_to_narrative: dict[str, str],
               account_by_post: dict[str, str | None]) -> tuple[dict, list[dict]]:
    groups: dict[str, list[GeoObservation]] = defaultdict(list)
    for observation in observations:
        if observation.location_name:
            key = observation.location_name.strip().casefold()
        elif observation.latitude is not None and observation.longitude is not None:
            key = f"{observation.latitude:.1f},{observation.longitude:.1f}"
        else:
            continue
        groups[key].append(observation)
    locations, points, anomalies = [], [], []
    suppressed_groups = suppressed_observations = 0
    minimum_group = settings.geo_min_group_size
    for key, rows in groups.items():
        # Count distinct observed accounts, not raw post volume. Unlinked posts
        # remain separate subjects so one prolific account cannot cross k.
        subjects = {account_by_post.get(row.post_id) or f"unlinked-post:{row.post_id or row.id}"
                    for row in rows}
        if len(subjects) < minimum_group:
            suppressed_groups += 1
            suppressed_observations += len(rows)
            continue
        dates = [_dt(row.observed_at) for row in rows if row.observed_at]
        size, timeline, undated = _timeline([(row.observed_at, row.id) for row in rows])
        lats = [row.latitude for row in rows if row.latitude is not None]
        lons = [row.longitude for row in rows if row.longitude is not None]
        exact_precision = {"reported_point", "gps", "exact", "device", "camera_position"}
        if any(row.precision in exact_precision for row in rows) and lats and lons:
            label = f"Approximate area {statistics.fmean(lats):.1f},{statistics.fmean(lons):.1f}"
        else:
            label = rows[0].location_name or f"Approximate area {key}"
        post_ids = sorted({row.post_id for row in rows if row.post_id})
        narrative_ids = sorted({post_to_narrative[p] for p in post_ids if p in post_to_narrative})
        baseline = [int(row["count"]) for row in timeline[-4:-1]] if len(timeline) >= 4 else []
        anomaly = None
        if len(baseline) == 3:
            latest = int(timeline[-1]["count"])
            mean = statistics.fmean(baseline)
            std = statistics.pstdev(baseline)
            if latest >= 3 and latest > mean + 2 * std and latest >= 2 * max(mean, 0.5):
                anomaly = {
                    "location": label,
                    "latest_count": latest,
                    "baseline_counts": baseline,
                    "baseline_mean": round(mean, 3),
                    "baseline_stddev": round(std, 3),
                    "bucket_size": size,
                    "evidence_ids": [row.id for row in rows[:50]],
                    "status": "review_spike",
                    "rule": "latest>=3 and latest>mean+2*population_stddev and latest>=2*max(mean,.5)",
                }
                anomalies.append(anomaly)
        item = {
            "key": key,
            "label": label,
            "observation_count": len(rows),
            "protected_subject_count": len(subjects),
            "post_count": len(post_ids),
            "narrative_ids": narrative_ids,
            "sources": sorted({row.source for row in rows}),
            "precisions": sorted({row.precision for row in rows}),
            "first_observed": _iso(min(dates)) if dates else None,
            "last_observed": _iso(max(dates)) if dates else None,
            "undated_observations": undated,
            "timeline": timeline,
            "baseline_status": "available" if len(baseline) == 3 else "insufficient_baseline",
            "anomaly": anomaly,
            "evidence_post_ids": post_ids[:50],
        }
        locations.append(item)
        if lats and lons:
            points.append({
                "key": key,
                "label": label,
                # Display aggregates at roughly city/area level, not an exact
                # person's point. Original source precision remains in the case.
                "latitude": round(statistics.fmean(lats), 2),
                "longitude": round(statistics.fmean(lons), 2),
                "count": len(rows),
                "intensity": min(1.0, len(rows) / 10),
                "anomaly": bool(anomaly),
            })
    locations.sort(key=lambda row: (bool(row["anomaly"]), row["observation_count"]), reverse=True)
    return {
        "points": points[:500],
        "locations": locations[:200],
        "anomalies": anomalies,
        "privacy": {
            "minimum_group_size": minimum_group,
            "suppressed_groups": suppressed_groups,
            "suppressed_observations": suppressed_observations,
            "basis": "Distinct observed accounts; unlinked posts are counted separately.",
        },
        "map_note": f"Heat points are aggregated, coordinates rounded to 2 decimals, and groups with fewer than {minimum_group} distinct observed subjects are suppressed. A source-reported place is not a live device or person location.",
    }, anomalies


def _evidence_confidence(alert: dict, posts_by_id: dict[str, Post],
                         accounts: dict[str, Account],
                         posts_by_account: dict[str, list[Post]]) -> dict:
    """Transparent completeness score, deliberately not a truth probability."""
    evidence_ids = [str(value) for value in (alert.get("evidence_ids") or [])]
    if alert.get("type") == "narrative_acceleration":
        evidence_posts = [posts_by_id[value] for value in evidence_ids if value in posts_by_id]
    elif alert.get("type") == "coordination_review":
        evidence_posts = [post for value in evidence_ids for post in posts_by_account.get(value, [])]
    else:
        return {"score": None, "level": "not_applicable",
                "score_type": "uncalibrated_evidence_completeness_not_truth_probability"}
    if not evidence_posts:
        return {"score": None, "level": "insufficient_evidence",
                "score_type": "uncalibrated_evidence_completeness_not_truth_probability"}
    platforms = {accounts[post.account_id].platform for post in evidence_posts
                 if post.account_id in accounts}
    timestamp_coverage = sum(post.timestamp is not None for post in evidence_posts) / len(evidence_posts)
    sample_factor = min(len(evidence_posts) / 20, 1)
    diversity_factor = min(len(platforms) / 2, 1)
    score = 100 * (0.30 * sample_factor + 0.30 * timestamp_coverage + 0.40 * diversity_factor)
    if len(platforms) <= 1:
        score = min(score, 60)
    score = round(score)
    return {
        "score": score,
        "level": "limited" if score < 40 else "moderate" if score < 70 else "comparatively_stronger",
        "score_type": "uncalibrated_evidence_completeness_not_truth_probability",
        "factors": {
            "visible_evidence_posts": len(evidence_posts),
            "source_timestamp_coverage": round(timestamp_coverage, 3),
            "platform_diversity_count": len(platforms),
        },
        "formula": "100*(.30*min(posts/20,1)+.30*timestamp_coverage+.40*min(platforms/2,1)); single/no-platform score capped at 60",
        "limitations": [
            "Measures visible evidence completeness only; it is not the probability that the alert interpretation is correct.",
            "Platform diversity is not proof of independent corroboration; access gaps and source bias remain.",
        ],
    }


def build_analytics(db: Session, case_id: str) -> dict:
    account_rows = db.scalars(select(Account).where(Account.case_id == case_id)).all()
    accounts = {account.id: account for account in account_rows}
    all_posts = db.scalars(select(Post).where(Post.case_id == case_id)).all()
    ordered_posts = sorted(all_posts, key=lambda p: _dt(p.timestamp) or _dt(p.created_at) or datetime.min.replace(tzinfo=UTC))
    posts = ordered_posts[-MAX_CLUSTER_POSTS:]
    truncated = len(all_posts) > len(posts)
    narratives, post_to_narrative = _build_narratives(posts, accounts, truncated)
    automation = _automation_indicators(posts, accounts)
    network = _build_network(db, case_id, accounts, posts)
    observations = db.scalars(select(GeoObservation).where(GeoObservation.case_id == case_id)).all()
    geo, geo_anomalies = _build_geo(
        observations, post_to_narrative, {post.id: post.account_id for post in all_posts})
    for narrative in narratives:
        narrative["locations"] = [location["label"] for location in geo["locations"] if narrative["id"] in location["narrative_ids"]]

    alerts = []
    for narrative in narratives:
        warning = narrative["early_warning"]
        if warning:
            alerts.append({
                "id": f"alert-{narrative['id']}", "type": "narrative_acceleration",
                "title": f"Narrative acceleration: {narrative['label']}",
                **warning,
                "narrative_id": narrative["id"],
                "recommended_action": "Review representative posts, source coverage and alternative explanations before response.",
                "limitations": ["A spike can reflect genuine breaking news or a data-collection change.", "Reference time is the latest collected observation, not guaranteed real time."],
            })
    candidates = db.scalars(select(CoordinationCandidate).where(CoordinationCandidate.case_id == case_id)).all()
    for candidate in candidates:
        alerts.append({
            "id": f"alert-coordination-{candidate.id}", "type": "coordination_review",
            "title": "Coordination candidate requires review", "severity": "review",
            "attention_score": 50, "score_type": "fixed_review_priority_not_probability",
            "narrative_id": None, "evidence_ids": json.loads(candidate.account_ids),
            "rule": "coordination workflow produced a review candidate",
            "recommended_action": "Inspect episodes, content rarity, timestamp precision and benign explanations.",
            "limitations": json.loads(candidate.alternatives),
        })
    for anomaly in geo_anomalies:
        alerts.append({
            "id": f"alert-geo-{hashlib.sha256(anomaly['location'].encode()).hexdigest()[:10]}",
            "type": "geospatial_spike", "title": f"Observed geo spike: {anomaly['location']}",
            "severity": "elevated", "attention_score": 60,
            "score_type": "fixed_review_priority_not_probability", "narrative_id": None,
            **anomaly,
            "recommended_action": "Check whether imports or breaking events changed coverage; corroborate location sources.",
            "limitations": ["Small or changing location samples can create apparent spikes.", "No person-level movement or live geolocation is inferred."],
        })
    access_rows = db.scalars(select(SourceAccess).where(SourceAccess.case_id == case_id)).all()
    failed: Counter[str] = Counter()
    for access in access_rows:
        if access.outcome in {"unavailable", "rate_limited", "login_required", "permission_denied", "not_configured"}:
            failed[f"{access.provider}:{access.outcome}"] += 1
    for key, count in failed.items():
        alerts.append({
            "id": f"alert-gap-{hashlib.sha256(key.encode()).hexdigest()[:10]}", "type": "data_coverage_gap",
            "title": f"Collection gap: {key}", "severity": "data_gap", "attention_score": None,
            "score_type": "not_applicable", "narrative_id": None, "evidence_ids": [],
            "rule": f"{count} source access record(s) have this outcome", "recommended_action": "Resolve access or mark corpus coverage as partial; do not interpret missing data as absence.",
            "limitations": [],
        })
    posts_by_id = {post.id: post for post in all_posts}
    posts_by_account: dict[str, list[Post]] = defaultdict(list)
    for post in all_posts:
        if post.account_id:
            posts_by_account[post.account_id].append(post)
    for alert in alerts:
        alert["evidence_confidence"] = _evidence_confidence(
            alert, posts_by_id, accounts, posts_by_account)
    severity_rank = {"high": 4, "elevated": 3, "review": 2, "data_gap": 1}
    alerts.sort(key=lambda alert: (severity_rank.get(alert["severity"], 0), alert.get("attention_score") or 0), reverse=True)
    alerts = sync_alerts(db, case_id, alerts)

    media_count = len(db.scalars(select(MediaAsset).where(MediaAsset.case_id == case_id)).all())
    dated_count = sum(1 for post in all_posts if post.timestamp)
    geo_post_ids = {row.post_id for row in observations if row.post_id}
    reference = max([_dt(post.timestamp) for post in all_posts if post.timestamp] or [None])
    return {
        "schema_version": "scamurai-analytics-v2",
        "generated_at": _iso(utcnow()),
        "reference_time": _iso(reference),
        "scope": "Collected case corpus only; analytics are refreshed on request and are not a platform-wide real-time monitor.",
        "coverage": {
            "posts": len(all_posts), "posts_analyzed_for_narratives": len(posts), "narrative_input_truncated": truncated,
            "accounts": len(accounts), "timestamped_posts": dated_count,
            "timestamp_coverage": round(dated_count / len(all_posts), 3) if all_posts else 0,
            "geolocated_posts": len(geo_post_ids), "media_assets": media_count,
            "source_access_records": len(access_rows),
        },
        "narratives": narratives,
        "automation": automation,
        "network": network,
        "geospatial": geo,
        "alerts": alerts[:100],
        "limitations": [
            "No numeric output is a calibrated probability of maliciousness, automation, deepfakes or campaign attribution.",
            "Narrative clusters are lexical candidates; multilingual sarcasm, code-switching and short texts need human review.",
            "Earliest observed is not first uploader; graph degree is not audience influence; source-reported geo is not live location.",
            "Organic discourse and coordinated campaigns can share the same surface features. Corroboration and reviewer decisions remain mandatory.",
        ],
    }


def build_account_detail(db: Session, case_id: str, account_id: str) -> dict | None:
    account = db.scalar(select(Account).where(Account.case_id == case_id, Account.id == account_id))
    if account is None:
        return None
    account_rows = db.scalars(select(Account).where(Account.case_id == case_id)).all()
    accounts = {row.id: row for row in account_rows}
    all_posts = db.scalars(select(Post).where(Post.case_id == case_id)).all()
    ordered = sorted(all_posts, key=lambda post: (
        _dt(post.timestamp) or _dt(post.created_at) or datetime.min.replace(tzinfo=UTC)))
    analysis_posts = ordered[-MAX_CLUSTER_POSTS:]
    own_posts = [post for post in ordered if post.account_id == account_id]
    behavior = next((row for row in _automation_indicators(analysis_posts, accounts)
                     if row["account_id"] == account_id), None)
    network = next((row for row in _build_network(db, case_id, accounts, analysis_posts)["nodes"]
                    if row["account_id"] == account_id), None)

    url_accounts: dict[str, set[str]] = defaultdict(set)
    for post in all_posts:
        if post.canonical_url and post.account_id:
            url_accounts[post.canonical_url].add(post.account_id)
    shared_urls = []
    for url, publishers in sorted(url_accounts.items()):
        if account_id in publishers and len(publishers) > 1:
            shared_urls.append({
                "url": url,
                "observed_account_count": len(publishers),
                "other_handles": sorted(accounts[value].handle for value in publishers
                                        if value != account_id and value in accounts),
                "note": "Exact shared source URL only; not evidence of common control.",
            })

    candidates = []
    for candidate in db.scalars(select(CoordinationCandidate).where(
            CoordinationCandidate.case_id == case_id)).all():
        if account_id not in json.loads(candidate.account_ids):
            continue
        candidates.append({
            "id": candidate.id,
            "review_state": candidate.review_state,
            "episodes": json.loads(candidate.episodes),
            "features": json.loads(candidate.features),
            "baseline": candidate.baseline,
            "alternatives": json.loads(candidate.alternatives),
            "created_at": _iso(candidate.created_at),
        })

    seen = [_dt(post.first_seen_at or post.created_at) for post in own_posts]
    collected = [_dt(post.collected_at or post.created_at) for post in own_posts]
    source_times = [_dt(post.timestamp) for post in own_posts if post.timestamp]
    returned = list(reversed(own_posts[-200:]))
    return {
        "account": {
            "id": account.id,
            "platform": account.platform,
            "platform_id": account.platform_id,
            "handle": account.handle,
            "display_name": account.display_name,
            "canonical_profile_url": account.canonical_profile_url,
            "observed_handles": json.loads(account.observed_handles),
            "identity_confirmed": account.identity_confirmed,
            "created_at": _iso(account.created_at),
        },
        "summary": {
            "post_count": len(own_posts),
            "timestamped_post_count": len(source_times),
            "language_counts": dict(Counter(post.language for post in own_posts)),
            "domain_counts": dict(Counter(urlparse(post.canonical_url).hostname or "unknown"
                                               for post in own_posts if post.canonical_url)),
            "first_source_timestamp": _iso(min(source_times)) if source_times else None,
            "last_source_timestamp": _iso(max(source_times)) if source_times else None,
            "first_seen_at": _iso(min(seen)) if seen else None,
            "last_collected_at": _iso(max(collected)) if collected else None,
            "shared_url_count": len(shared_urls),
        },
        "behavior": behavior,
        "network": network,
        "shared_urls": shared_urls[:50],
        "coordination_candidates": candidates,
        "posts": [{
            "id": post.id,
            "source_id": post.source_id,
            "text": post.raw_text,
            "url": post.canonical_url,
            "language": post.language,
            "source_timestamp": _iso(post.timestamp),
            "timestamp_precision": post.timestamp_precision,
            "first_seen_at": _iso(post.first_seen_at or post.created_at),
            "collected_at": _iso(post.collected_at or post.created_at),
            "collection_status": post.collection_status,
        } for post in returned],
        "coverage": {
            "posts_returned": len(returned),
            "posts_total": len(own_posts),
            "truncated": len(own_posts) > len(returned),
            "analysis_post_cap": MAX_CLUSTER_POSTS,
            "case_posts": len(all_posts),
        },
        "limitations": [
            "Earliest observed and collection times describe this case corpus, not platform-wide origin or full account history.",
            "Shared URLs, timing and graph centrality do not establish common ownership, coordination or automation.",
            "Only public/source-supplied account metadata is shown; no private account access or person-level tracking is performed.",
        ],
    }
