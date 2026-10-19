"""Graph construction and queries over relational node/edge tables.

Every edge is validated against RELATIONSHIPS and carries a derivation class.
Layout (pin/position) is stored on nodes only and can never create a relation.
"""
from __future__ import annotations

import json
from collections import deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import GraphEdge, GraphNode
from ..registry import EVIDENCE, RELATIONSHIPS, RelationshipSpec


def _node_key(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def upsert_node(
    db: Session,
    case_id: str,
    entity_type: str,
    entity_id: str,
    label: str,
    properties: dict | None = None,
) -> GraphNode:
    existing = db.scalar(
        select(GraphNode).where(
            GraphNode.case_id == case_id,
            GraphNode.entity_type == entity_type,
            GraphNode.entity_id == entity_id,
        )
    )
    if existing:
        return existing
    node = GraphNode(
        case_id=case_id,
        entity_type=entity_type,
        entity_id=entity_id,
        label=label[:500],
        properties=json.dumps(properties or {}),
    )
    db.add(node)
    db.flush()
    return node


def add_edge(
    db: Session,
    case_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship: str,
    evidence_ids: list[str] | None = None,
    analysis_run_id: str | None = None,
    statement: str = "",
    time_interval: str | None = None,
) -> GraphEdge | None:
    """Idempotent edge creation; invalid entity pairs are rejected, not guessed."""
    spec: RelationshipSpec = RELATIONSHIPS[relationship]
    if source_type not in spec.source_types or target_type not in spec.target_types:
        raise ValueError(
            f"Relationship {relationship} cannot connect {source_type} -> {target_type}"
        )
    src = upsert_node(db, case_id, source_type, source_id, source_id)
    dst = upsert_node(db, case_id, target_type, target_id, target_id)
    idem = f"{src.id}->{dst.id}:{relationship}"
    existing = db.scalar(
        select(GraphEdge).where(
            GraphEdge.case_id == case_id, GraphEdge.idempotency_key == idem
        )
    )
    if existing:
        return existing
    edge = GraphEdge(
        case_id=case_id,
        source_node_id=src.id,
        target_node_id=dst.id,
        relationship=relationship,
        derivation_class=spec.derivation_class,
        evidence_ids=json.dumps(evidence_ids or []),
        analysis_run_id=analysis_run_id,
        statement=statement,
        time_interval=time_interval,
        idempotency_key=idem,
    )
    db.add(edge)
    db.flush()
    return edge


def evidence_node(db: Session, record) -> GraphNode:
    """Every evidence record gets a graph node so findings can resolve to it."""
    return upsert_node(
        db, record.case_id, EVIDENCE, record.id,
        f"evidence:{record.source_kind}:{record.id[:8]}",
        {"method": record.method, "source_kind": record.source_kind,
         "object_hash": record.object_hash})


def serialize_node(node: GraphNode) -> dict:
    return {
        "id": node.id,
        "entity_type": node.entity_type,
        "entity_id": node.entity_id,
        "label": node.label,
        "properties": json.loads(node.properties),
        "pinned": node.pinned,
    }


def serialize_edge(edge: GraphEdge) -> dict:
    return {
        "id": edge.id,
        "source": edge.source_node_id,
        "target": edge.target_node_id,
        "relationship": edge.relationship,
        "derivation_class": edge.derivation_class,
        "evidence_ids": json.loads(edge.evidence_ids),
        "analysis_run_id": edge.analysis_run_id,
        "statement": edge.statement,
        "time_interval": edge.time_interval,
    }


def get_graph(
    db: Session, case_id: str, relation_types: list[str] | None = None,
    limit_nodes: int = 400, limit_edges: int = 800,
) -> dict:
    nodes = db.scalars(
        select(GraphNode).where(GraphNode.case_id == case_id).limit(limit_nodes)
    ).all()
    edge_q = select(GraphEdge).where(GraphEdge.case_id == case_id)
    if relation_types:
        edge_q = edge_q.where(GraphEdge.relationship.in_(relation_types))
    edges = db.scalars(edge_q.limit(limit_edges)).all()
    node_count = len(db.scalars(select(GraphNode).where(GraphNode.case_id == case_id)).all())
    edge_count = len(db.scalars(select(GraphEdge).where(GraphEdge.case_id == case_id)).all())
    return {
        "nodes": [serialize_node(n) for n in nodes],
        "edges": [serialize_edge(e) for e in edges],
        "truncated": node_count > limit_nodes or edge_count > limit_edges,
        "total_nodes": node_count,
        "total_edges": edge_count,
    }


def shortest_known_evidence_path(
    db: Session, case_id: str, source_node_id: str, target_node_id: str,
    max_depth: int, max_nodes: int,
) -> list[dict]:
    """BFS navigation aid — explicitly not proof of shared ownership/intent."""
    edges = db.scalars(select(GraphEdge).where(GraphEdge.case_id == case_id)).all()
    adjacency: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_node_id, []).append(edge)
        adjacency.setdefault(edge.target_node_id, []).append(edge)

    visited = {source_node_id}
    queue: deque[tuple[str, list[GraphEdge], int]] = deque([(source_node_id, [], 0)])
    while queue:
        current, path, depth = queue.popleft()
        if current == target_node_id:
            return [serialize_edge(e) for e in path]
        if depth >= max_depth or len(visited) >= max_nodes:
            continue
        for edge in adjacency.get(current, []):
            nxt = edge.target_node_id if edge.source_node_id == current else edge.source_node_id
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [edge], depth + 1))
    return []
