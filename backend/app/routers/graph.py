"""Graph workspace, shortest known evidence path and account comparison."""
from __future__ import annotations

from itertools import combinations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, GraphEdge, GraphNode, Post
from ..registry import ACCOUNT
from ..schemas import GraphOut, PathRequest
from ..security import require_case
from ..services import graph as graph_svc

router = APIRouter(prefix="/api/v1/cases/{case_id}", tags=["graph"])


@router.get("/graph", response_model=GraphOut)
def get_graph(relation_types: str | None = None,
              ctx=Depends(require_case()), db: Session = Depends(get_db)):
    filters = [r.strip() for r in relation_types.split(",")] if relation_types else None
    return graph_svc.get_graph(db, ctx.case.id, filters)


@router.post("/graph/path")
def shortest_path(body: PathRequest, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    path = graph_svc.shortest_known_evidence_path(
        db, ctx.case.id, body.source_node_id, body.target_node_id,
        body.max_depth, body.max_nodes)
    return {
        "edges": path,
        "disclaimer": "Navigation aid only — a path does not prove shared ownership or intent.",
        "found": bool(path),
    }


@router.post("/graph/nodes/{node_id}/pin")
def pin_node(node_id: str, pinned: bool = True,
             ctx=Depends(require_case({"analyst", "owner"})), db: Session = Depends(get_db)):
    node = db.get(GraphNode, node_id)
    if node is None or node.case_id != ctx.case.id:
        return {"ok": False}
    node.pinned = pinned  # layout state never creates relationships
    db.commit()
    return {"ok": True, "node_id": node_id, "pinned": pinned}


@router.get("/compare")
def compare_accounts(account_ids: str, ctx=Depends(require_case()),
                     db: Session = Depends(get_db)):
    """Complete pairwise matrix for a small explicitly selected account set."""
    ids = [a.strip() for a in account_ids.split(",") if a.strip()]
    if len(ids) < 2 or len(ids) > 6:
        return {"error": "Select between 2 and 6 accounts"}
    accounts = db.scalars(select(Account).where(
        Account.case_id == ctx.case.id, Account.id.in_(ids))).all()
    by_id = {a.id: a for a in accounts}
    posts = db.scalars(select(Post).where(
        Post.case_id == ctx.case.id, Post.account_id.in_(ids))).all()
    edges = db.scalars(select(GraphEdge).where(GraphEdge.case_id == ctx.case.id)).all()
    nodes = {n.id: n for n in db.scalars(select(GraphNode).where(
        GraphNode.case_id == ctx.case.id, GraphNode.entity_type == ACCOUNT)).all()}
    pairs = []
    for a_id, b_id in combinations(ids, 2):
        a, b = by_id.get(a_id), by_id.get(b_id)
        if not a or not b:
            continue
        a_posts = [p for p in posts if p.account_id == a_id]
        b_posts = [p for p in posts if p.account_id == b_id]
        shared_text = [
            x.normalized_text[:60]
            for x in a_posts for y in b_posts
            if x.normalized_text and x.normalized_text == y.normalized_text
        ]
        crosslink = any(
            e.relationship == "PUBLICLY_CROSSLINKS"
            and {nodes[e.source_node_id].entity_id if e.source_node_id in nodes else None,
                 nodes[e.target_node_id].entity_id if e.target_node_id in nodes else None}
            == {a_id, b_id}
            for e in edges)
        timing = "unknown precision — minute synchronization not inferable"
        precise = [p.timestamp for p in a_posts + b_posts
                   if p.timestamp and p.timestamp_precision == "minute"]
        if precise:
            timing = f"{len(precise)} minute-precision timestamps available"
        pairs.append({
            "pair": [a.handle, b.handle],
            "identity_verified": a.identity_confirmed and b.identity_confirmed,
            "shared_content": sorted(set(shared_text)),
            "explicit_public_crosslinks": crosslink,
            "timing_indicators": timing,
            "contradictory_or_insufficient": [
                "Display-name similarity is not identity evidence." if not crosslink else
                "Cross-link is source-attributed; impersonation remains possible.",
                "Shared viral content has ordinary (non-coordinated) explanations.",
            ],
        })
    return {"account_count": len(ids), "pair_count": len(pairs),
            "disclaimer": "Link analysis and content correlation — not entity resolution to one person.",
            "pairs": pairs}
