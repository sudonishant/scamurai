"""Case-scoped public account inventory and evidence detail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, Post
from ..security import require_case
from ..services.analytics import build_account_detail

router = APIRouter(prefix="/api/v1/cases/{case_id}/accounts", tags=["accounts"])


@router.get("")
def accounts(q: str = Query(default="", max_length=200),
             ctx=Depends(require_case()), db: Session = Depends(get_db)):
    query = select(Account).where(Account.case_id == ctx.case.id)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where((Account.handle.ilike(pattern)) |
                            (Account.display_name.ilike(pattern)) |
                            (Account.platform.ilike(pattern)))
    rows = db.scalars(query.order_by(Account.handle).limit(500)).all()
    counts = db.execute(select(
        Post.account_id, func.count(Post.id), func.max(Post.timestamp), func.max(Post.collected_at),
    ).where(Post.case_id == ctx.case.id).group_by(Post.account_id)).all()
    stats = {account_id: (count, last_source, last_collected)
             for account_id, count, last_source, last_collected in counts}
    return [{
        "id": row.id,
        "platform": row.platform,
        "handle": row.handle,
        "display_name": row.display_name,
        "canonical_profile_url": row.canonical_profile_url,
        "identity_confirmed": row.identity_confirmed,
        "post_count": stats.get(row.id, (0, None, None))[0],
        "last_source_timestamp": stats.get(row.id, (0, None, None))[1],
        "last_collected_at": stats.get(row.id, (0, None, None))[2],
    } for row in rows]


@router.get("/{account_id}")
def account_detail(account_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    result = build_account_detail(db, ctx.case.id, account_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    return result
