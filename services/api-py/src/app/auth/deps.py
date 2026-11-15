"""FastAPI dependencies: authenticate, pick the practice, check the role,
and open the tenant-scoped session.

Expects on app.state: `verifier` (TokenVerifier) and `pg_engine` (SQLAlchemy
engine connected as the RLS-bound app role).
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.tenancy.models import Role, UserAccount
from app.tenancy.session import bind_practice, global_session

from .verifier import AuthError, Principal


@dataclass(frozen=True)
class CurrentMember:
    user_id: UUID
    member_id: UUID
    practice_id: UUID
    role: Role


def current_principal(request: Request) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    try:
        return request.app.state.verifier.verify(token)
    except AuthError as exc:
        raise HTTPException(401, f"invalid token: {exc}",
                            headers={"WWW-Authenticate": "Bearer"}) from exc


def upsert_user(engine, principal: Principal, memberships_out: list | None = None) -> UUID:
    """Find or create the account. When `memberships_out` is given the caller's memberships
    are read in the same transaction (one pool checkout and one commit instead of two: each
    is a database round trip several times over on a managed Postgres)."""
    with global_session(engine) as s:
        user = s.scalar(select(UserAccount).where(
            UserAccount.issuer == principal.issuer, UserAccount.subject == principal.subject))
        if user is None:
            user = UserAccount(issuer=principal.issuer, subject=principal.subject,
                               email=principal.email, phone=principal.phone,
                               display_name=principal.name)
            s.add(user)
            s.flush()
        elif user.deleted_at is not None:
            raise HTTPException(403, "account disabled")
        if memberships_out is not None:
            rows = s.execute(text("SELECT * FROM app_memberships(:u)"), {"u": user.id}).mappings()
            memberships_out.extend(dict(r) for r in rows)
        return user.id


def memberships(engine, user_id: UUID) -> list[dict]:
    with global_session(engine) as s:
        rows = s.execute(text("SELECT * FROM app_memberships(:u)"), {"u": user_id}).mappings()
        return [dict(r) for r in rows]


def current_user_id(request: Request, principal: Principal = Depends(current_principal)) -> UUID:
    auth = getattr(request.app.state, "auth", None)
    if principal.session_id and auth is not None and not auth.session_active(principal.session_id):
        raise HTTPException(401, "session was signed out", headers={"WWW-Authenticate": "Bearer"})
    rows: list = []
    user_id = upsert_user(request.app.state.pg_engine, principal, rows)
    request.state.memberships = (user_id, rows)  # read by current_member, this request only
    return user_id


def current_member(
    request: Request,
    user_id: UUID = Depends(current_user_id),
    principal: Principal = Depends(current_principal),
    x_practice_id: str | None = Header(default=None),
) -> CurrentMember:
    cached = getattr(request.state, "memberships", None)
    rows = (list(cached[1]) if cached is not None and cached[0] == user_id
            else memberships(request.app.state.pg_engine, user_id))
    if not x_practice_id and len(rows) > 1 and principal.session_id:
        # "Switch practice" is remembered on the session when no header is sent.
        chosen = request.app.state.auth.session_practice(principal.session_id)
        if chosen is not None and any(r["practice_id"] == chosen for r in rows):
            x_practice_id = str(chosen)
    if x_practice_id:
        try:
            wanted = UUID(x_practice_id)
        except ValueError:
            raise HTTPException(400, "X-Practice-Id must be a UUID") from None
        rows = [r for r in rows if r["practice_id"] == wanted]
        if not rows:
            raise HTTPException(403, "not a member of that practice")
    elif not rows:
        raise HTTPException(403, "user has no practice membership")
    elif len(rows) > 1:
        raise HTTPException(400, "send X-Practice-Id (member of several practices)")
    row = rows[0]
    return CurrentMember(user_id=user_id, member_id=row["member_id"],
                         practice_id=row["practice_id"], role=Role(row["role"]))


def require_roles(*roles: Role) -> Callable[..., CurrentMember]:
    """Dependency factory: Depends(require_roles(Role.owner, Role.astrologer))."""

    def checker(member: CurrentMember = Depends(current_member)) -> CurrentMember:
        if member.role not in roles:
            raise HTTPException(403, f"requires role: {', '.join(r.value for r in roles)}")
        return member

    return checker


def tenant_db(request: Request,
              member: CurrentMember = Depends(current_member)) -> Iterator[Session]:
    """Session bound to the caller's practice (SET LOCAL app.practice_id).

    Routes must use Depends(tenant_db, scope="function") (FastAPI >= 0.121): with the default
    request scope the commit runs after the response is sent, so a fast follow-up request on
    another connection can miss the row that was just created (flaky 404 on a new client).
    """
    with Session(request.app.state.pg_engine, expire_on_commit=False) as session:
        with session.begin():
            bind_practice(session, member.practice_id)
            yield session
