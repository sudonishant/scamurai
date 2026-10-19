"""Authentication, RBAC, case isolation and input-defence helpers.

Master prompt sections 4, 17 and 19. The dev token scheme is intentional and
labeled in the UI/API docs — it must be replaced by an external identity
provider before any real deployment.
"""
from __future__ import annotations

import html
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Case, CaseMembership, User

ROLE_RANK = {"viewer": 1, "reviewer": 2, "analyst": 3, "owner": 4}
WRITE_ROLES = {"analyst", "owner"}
REVIEW_ROLES = {"reviewer", "owner"}

# Magic-byte signatures — extensions are never trusted on their own.
IMAGE_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # plus 'WEBP' at offset 8
}

settings = get_settings()


# --------------------------------------------------------------------- auth
def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = db.scalar(select(User).where(User.dev_token == token))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return user


@dataclass
class CaseContext:
    case: Case
    user: User
    role: str


def get_case_context(case_id: str, db: Session, user: User) -> CaseContext:
    # 404 (not 403) for unknown or intentionally concealed resources.
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    membership = db.scalar(
        select(CaseMembership).where(
            CaseMembership.case_id == case_id,
            CaseMembership.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return CaseContext(case=case, user=user, role=membership.role)


def require_case(required_roles: set[str] | None = None):
    """Dependency factory: membership is checked on every read and write."""

    def _dep(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        ctx = get_case_context(case_id, db, user)
        if required_roles and ROLE_RANK[ctx.role] < min(ROLE_RANK[r] for r in required_roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{ctx.role}' cannot perform this action")
        return ctx

    return _dep


# --------------------------------------------------------------------- SSRF
_BLOCKED_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),     # link-local incl. cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)
_METADATA_HOSTS = {"metadata.google.internal", "metadata", "169.254.169.254"}


def assert_public_url(url: str) -> str:
    """Validate an outbound URL against SSRF rules *before* any fetch.

    Re-validated after redirects by the connector layer. Raises 422 on policy
    violation so the attempt is visible rather than silently dropped.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Only http/https URLs are allowed")
    host = parsed.hostname
    if not host:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "URL has no host")
    if host in _METADATA_HOSTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Blocked target")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Host cannot be resolved")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if any(ip in net for net in _BLOCKED_NETWORKS):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Blocked private/link-local target")
    return url


# --------------------------------------------------------------------- uploads
def validate_image_signature(data: bytes) -> str:
    for mime, sigs in IMAGE_SIGNATURES.items():
        if any(data.startswith(sig) for sig in sigs):
            if mime == "image/webp" and data[8:12] != b"WEBP":
                continue
            return mime
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File content is not a supported image")


# --------------------------------------------------------------------- output safety
def csv_safe(value: object) -> str:
    """Neutralize CSV formula injection (section 19)."""
    text = "" if value is None else str(value)
    if text and text[0] in {"=", "+", "-", "@", "\t", "\r"}:
        text = "'" + text
    return text


def safe_html(value: object) -> str:
    return html.escape("" if value is None else str(value))


def mask_identifier(value: str | None) -> str:
    if not value:
        return "unavailable"
    if len(value) <= 3:
        return value[:1] + "**"
    return value[:2] + "*" * max(3, len(value) - 4) + value[-2:]
