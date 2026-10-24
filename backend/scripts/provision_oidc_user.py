"""Provision an external OIDC identity without granting implicit case access.

Run from backend/ after Alembic upgrade:
  python scripts/provision_oidc_user.py --email analyst@example.org \
    --name "Analyst" --issuer https://idp.example.org/ --subject subject-id
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Case, CaseMembership, User
from app.services.audit import record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--role", choices=["viewer", "reviewer", "analyst", "owner"])
    args = parser.parse_args()
    if args.role and not args.case_id:
        parser.error("--role requires --case-id")

    with SessionLocal() as db:
        duplicate = db.scalar(select(User).where(
            User.auth_issuer == args.issuer, User.auth_subject == args.subject))
        user = db.scalar(select(User).where(User.email == args.email))
        if duplicate is not None and (user is None or duplicate.id != user.id):
            raise SystemExit("That issuer/subject is already provisioned for another user")
        if user is None:
            user = duplicate or User(email=args.email, name=args.name)
            db.add(user)
        user.email = args.email
        user.name = args.name
        user.auth_issuer = args.issuer
        user.auth_subject = args.subject
        # Existing development tokens remain in the row for migration history,
        # but are unusable whenever DEV_AUTH_ENABLED=false.
        db.flush()
        record(db, user.id, "identity.provision", "user", user.id, None,
               {"issuer": args.issuer})

        if args.case_id:
            case = db.get(Case, args.case_id)
            if case is None:
                raise SystemExit("Case not found; user changes were not committed")
            membership = db.scalar(select(CaseMembership).where(
                CaseMembership.case_id == case.id, CaseMembership.user_id == user.id))
            if membership is None:
                membership = CaseMembership(case_id=case.id, user_id=user.id,
                                            role=args.role or "viewer")
                db.add(membership)
            elif args.role:
                membership.role = args.role
            record(db, user.id, "case.membership.provision", "case", case.id, case.id,
                   {"member_user_id": user.id, "role": membership.role})
        db.commit()
        print(f"Provisioned {user.email} (user {user.id}); no bearer token was created.")


if __name__ == "__main__":
    main()
