"""Possible-coordination detection (master prompt section 13).

Three questions are kept separate at every step:
  1. Are activities aligned?            (observable behavior, measured here)
  2. Are the shared claims true/false?  (claim workflow, never merged)
  3. Is deceptive intent established?   (generally needs evidence beyond content)

Candidate generation uses inverted indexes (shared content / URLs / visuals /
time buckets) instead of all-pairs comparison. A single shared image, hashtag
or news event can never produce a coordination candidate on its own.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    Account,
    CoordinationCandidate,
    GraphEdge,
    GraphNode,
    Post,
)
from ..registry import ACCOUNT, COORDINATION, MEDIA, POST
from . import graph
from .textutil import normalize_text, normalize_url

settings = get_settings()
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
HASHTAG_RE = re.compile(r"#[\w]+", re.IGNORECASE)


def _distinctive_tokens(text: str) -> set[str]:
    return {t for t in normalize_text(text).split() if len(t) > 4}


def _timing_gap(posts: list[Post], window_minutes: int) -> dict:
    """Minute-level timing only when precision supports it."""
    precise = [p for p in posts if p.timestamp is not None and p.timestamp_precision == "minute"]
    day_only = [p for p in posts if p.timestamp_precision == "day"]
    if len(precise) >= 2:
        precise.sort(key=lambda p: p.timestamp)
        gap = (precise[-1].timestamp - precise[0].timestamp).total_seconds() / 60
        return {
            "min_gap_minutes": round(gap, 2),
            "within_window": gap <= window_minutes,
            "window_minutes": window_minutes,
            "timing_feature": "measured",
        }
    if day_only:
        return {"min_gap_minutes": None, "within_window": None,
                "timing_feature": "not_inferable_day_precision"}
    return {"min_gap_minutes": None, "within_window": None,
            "timing_feature": "missing_timestamps_count_as_unknown_not_zero"}


def _compute_qut_coortweet_sync(posts: list[Post], account_a: str, account_b: str) -> dict:
    """Compute QUT Coordination Network Toolkit & CooRTweet reciprocal delta-t coordination weight."""
    posts_a = [p for p in posts if p.account_id == account_a and p.timestamp is not None]
    posts_b = [p for p in posts if p.account_id == account_b and p.timestamp is not None]
    if not posts_a or not posts_b:
        return {"status": "insufficient_timestamped_actions", "coordination_weight": 0.0}

    time_diffs_sec = []
    for pa in posts_a:
        diffs = [abs((pa.timestamp - pb.timestamp).total_seconds()) for pb in posts_b]
        if diffs:
            time_diffs_sec.append(min(diffs))

    if not time_diffs_sec:
        return {"status": "no_comparable_events", "coordination_weight": 0.0}

    weights = [1.0 / (sec + 1.0) for sec in time_diffs_sec]
    total_weight = sum(weights)
    fastest = min(time_diffs_sec)
    mean_gap = sum(time_diffs_sec) / len(time_diffs_sec)
    sub_60s = sum(1 for sec in time_diffs_sec if sec <= 60.0)

    return {
        "coordination_weight": round(total_weight, 4),
        "fastest_sync_seconds": round(fastest, 2),
        "mean_sync_seconds": round(mean_gap, 2),
        "synchronized_actions_under_60s": sub_60s,
        "algorithm": "QUT CNT & CooRTweet: Sum of reciprocal delta-t time gaps W = sum(1 / (dt_sec + 1))",
        "interpretation": "Values >= 1.0 with sub-60s gaps indicate non-random temporal synchronization of content propagation.",
    }


def _media_event_index(db: Session, case_id: str) -> dict[str, set[str]]:
    """Map account_id -> visual event ids derived from match edges + post links."""
    edges = db.scalars(select(GraphEdge).where(
        GraphEdge.case_id == case_id,
        GraphEdge.relationship.in_(["EXACT_FILE_MATCH", "VISUAL_SOURCE_MATCH"]))).all()
    media_groups: list[set[str]] = []
    for edge in edges:
        placed = False
        for group in media_groups:
            if edge.source_node_id in group or edge.target_node_id in group:
                group.update({edge.source_node_id, edge.target_node_id})
                placed = True
                break
        if not placed:
            media_groups.append({edge.source_node_id, edge.target_node_id})

    node_rows = db.scalars(select(GraphEdge).where(GraphEdge.case_id == case_id)).all()
    # map media entity -> posts through CONTAINS_MEDIA edges
    media_to_posts: dict[str, set[str]] = defaultdict(set)
    for edge in node_rows:
        if edge.relationship == "CONTAINS_MEDIA":
            media_to_posts[edge.target_node_id].add(edge.source_node_id)
    nodes = {n.id: n for n in db.scalars(
        select(GraphNode).where(GraphNode.case_id == case_id)).all()}
    account_events: dict[str, set[str]] = defaultdict(set)
    for gi, group in enumerate(media_groups):
        for node_id in group:
            node = nodes.get(node_id)
            if not node or node.entity_type != MEDIA:
                continue
            for post_node_id in media_to_posts.get(node_id, set()):
                post_node = nodes.get(post_node_id)
                if post_node and post_node.entity_type == POST:
                    post = db.get(Post, post_node.entity_id)
                    if post and post.account_id:
                        account_events[post.account_id].add(f"visual:{gi}")
    return account_events


def detect(db: Session, case_id: str, window_minutes: int | None = None) -> dict:
    window = window_minutes or settings.coordination_window_minutes
    posts = db.scalars(select(Post).where(Post.case_id == case_id)).all()
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.case_id == case_id)).all()}
    total = max(len(posts), 1)
    _ = accounts  # account lookup kept for readability of downstream pair resolution

    # --- inverted indexes: content event -> account ids, with event metadata
    events: dict[str, dict] = {}
    pair_events: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_posts: dict[tuple[str, str], list[Post]] = defaultdict(list)

    def index_event(event_id: str, participants: list[tuple[str, Post]], rarity: float,
                    event_kind: str, strong: bool, upstream_shared: bool = False):
        events[event_id] = {"kind": event_kind, "rarity": rarity, "strong": strong,
                            "participants": [a for a, _ in participants],
                            "upstream_shared": upstream_shared}
        for (a1, p1), (a2, p2) in combinations(participants, 2):
            if a1 == a2:
                continue
            key = tuple(sorted((a1, a2)))
            pair_events[key].add(event_id)
            pair_posts[key].extend([p1, p2])

    # 1) exact normalized-text groups
    text_groups: dict[str, list[Post]] = defaultdict(list)
    for post in posts:
        if post.normalized_text:
            text_groups[post.normalized_text].append(post)
    for text, group in text_groups.items():
        owners = {(p.account_id, p) for p in group if p.account_id}
        if len({a for a, _ in owners}) < 2:
            continue
        distinctive = len(_distinctive_tokens(text)) >= 6
        rarity = len(group) / total
        # Strong only when BOTH distinctive AND rare: generic breaking-news
        # lines reused by many accounts are weak convergence, not coordination.
        is_strong = distinctive and rarity <= 0.25
        index_event(f"text-exact:{text[:40]}", list(owners), rarity,
                    "exact_text", strong=is_strong, upstream_shared=not is_strong)

    # 2) near-duplicate text (bounded: only posts sharing a distinctive token)
    token_index: dict[str, list[Post]] = defaultdict(list)
    for post in posts:
        for token in _distinctive_tokens(post.raw_text):
            token_index[token].append(post)
    seen_pairs: set[tuple[str, str]] = set()
    for candidates in token_index.values():
        for p1, p2 in combinations(candidates, 2):
            key = tuple(sorted((p1.id, p2.id)))
            if key in seen_pairs or p1.account_id == p2.account_id or not p1.account_id:
                continue
            seen_pairs.add(key)
            n1, n2 = p1.normalized_text, p2.normalized_text
            # Identical text is already indexed as an exact-text event.
            if n1 == n2:
                continue
            # Guard against common-word false positives: near-duplicates must be
            # long, similar in length, and very close lexically.
            if len(n1.split()) < 8 or min(len(n1), len(n2)) / max(len(n1), len(n2)) < 0.7:
                continue
            ratio = SequenceMatcher(None, n1, n2).ratio()
            if ratio >= max(settings.near_duplicate_ratio, 0.90):
                index_event(f"text-near:{key[0][:8]}:{key[1][:8]}",
                            [(p1.account_id, p1), (p2.account_id, p2)],
                            rarity=2 / total, event_kind="near_duplicate_text", strong=True)

    # 3) shared normalized destination URLs (tracking params removed)
    url_groups: dict[str, list[Post]] = defaultdict(list)
    for post in posts:
        for raw_url in URL_RE.findall(post.raw_text or ""):
            url_groups[normalize_url(raw_url)].append(post)
    for url, group in url_groups.items():
        owners = {(p.account_id, p) for p in group if p.account_id}
        if len({a for a, _ in owners}) >= 2:
            index_event(f"url:{url[:48]}", list(owners), len(group) / total,
                        "shared_url", strong=False, upstream_shared=True)

    # 4) visual-source groups from the image pipeline
    visual_events = _media_event_index(db, case_id)
    visual_by_event: dict[str, set[str]] = defaultdict(set)
    for account_id, evs in visual_events.items():
        for ev in evs:
            visual_by_event[ev].add(account_id)
    for ev, account_ids in visual_by_event.items():
        if len(account_ids) >= 2:
            participants = [(aid, next(p for p in posts if p.account_id == aid))
                            for aid in account_ids
                            if any(p.account_id == aid for p in posts)]
            index_event(f"visual:{ev}", participants, len(account_ids) / total,
                        "visual_source", strong=True, upstream_shared=False)

    # --- candidate generation with repeated-episode rule
    created = 0
    insufficient = 0
    hashtag_heavy = len(HASHTAG_RE.findall(" ".join(p.raw_text or "" for p in posts)))
    for pair, event_ids in pair_events.items():
        account_a, account_b = pair
        timing = _timing_gap(pair_posts[pair], window)
        event_kinds = [events[e]["kind"] for e in event_ids]
        strong_events = [e for e in event_ids if events[e]["strong"]]
        rare_strong = [e for e in strong_events if events[e]["rarity"] <= 0.25]
        repeated_episodes = len(event_ids) >= 2
        tight_timing = timing.get("within_window") is True
        # Repeated alignment needs at least one STRONG episode; hashtag/news
        # convergence alone (weak events) stays insufficient evidence.
        repeated_strong = repeated_episodes and bool(strong_events)
        single_rare = len(event_ids) == 1 and bool(rare_strong) and tight_timing
        only_generic = all(events[e]["upstream_shared"] for e in event_ids)

        alternatives = [
            "ordinary breaking-news convergence around the same public event",
            "viral template / popular hashtag reuse",
            "authorized scheduled syndication or republishing of one upstream source",
        ]
        if not (repeated_strong or single_rare) or (only_generic and not tight_timing):
            review_state = "insufficient_evidence"
            insufficient += 1
        else:
            review_state = "review_candidate"
        qut_sync = _compute_qut_coortweet_sync(pair_posts[pair], account_a, account_b)
        features = {
            "shared_episodes": sorted(event_ids),
            "episode_count": len(event_ids),
            "event_kinds": event_kinds,
            "timing": timing,
            "qut_coortweet_metrics": qut_sync,
            "hashtag_occurrences_in_corpus": hashtag_heavy,
            "corpus_size": len(posts),
            "baseline": "corpus-only baseline; no external platform-wide comparison",
        }
        candidate = CoordinationCandidate(
            case_id=case_id, account_ids=json.dumps(list(pair)),
            date_from=min((p.timestamp for p in pair_posts[pair] if p.timestamp), default=None),
            date_to=max((p.timestamp for p in pair_posts[pair] if p.timestamp), default=None),
            episodes=json.dumps(sorted(event_ids)),
            features=json.dumps(features, default=str),
            alternatives=json.dumps(alternatives),
            review_state=review_state,
        )
        db.add(candidate)
        db.flush()
        if review_state == "review_candidate":
            graph.upsert_node(db, case_id, COORDINATION, candidate.id,
                              "Coordination candidate (review)",
                              {"state": review_state, "episodes": len(event_ids)})
            graph.add_edge(db, case_id, COORDINATION, candidate.id, ACCOUNT, account_a,
                           "POSSIBLY_COORDINATED_WITH",
                           statement="Hypothesis from repeated aligned behavior; intent not established",
                           time_interval=json.dumps(timing))
            graph.add_edge(db, case_id, COORDINATION, candidate.id, ACCOUNT, account_b,
                           "POSSIBLY_COORDINATED_WITH",
                           statement="Hypothesis from repeated aligned behavior; intent not established",
                           time_interval=json.dumps(timing))
            created += 1
    return {"candidates_review": created, "insufficient_pairs": insufficient,
            "pairs_considered": len(pair_events), "window_minutes": window}
