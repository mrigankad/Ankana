"""Built-in authentication: one-time codes, passwords, sessions, invites, OIDC.

All state lives in Postgres so any number of API replicas agree (rate limits
are counted from the append-only auth_event table, not process memory).
Methods are synchronous and open their own short transactions; failures that
must be recorded (bad code, bad password) are committed before the error is
raised.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app import metrics
from app.tenancy.models import (
    AuditEvent,
    AuthEvent,
    AuthIdentity,
    AuthOtp,
    AuthSession,
    Client,
    Member,
    Practice,
    PracticeInvite,
    Role,
    UserAccount,
    UserCredential,
)
from app.tenancy.session import bind_practice, global_session
from app.v1.common import ProblemError

from .config import BUILTIN_ISSUER_KEY, AuthConfig
from .keys import Issuer
from .mailer import Mailer, MailError, Message, SmsSender
from .passwords import (
    DUMMY_HASH,
    PasswordPolicyError,
    check_policy,
    hash_password,
    needs_rehash,
    verify_password,
)

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
STAFF_ROLES = (Role.owner, Role.astrologer, Role.assistant)


def now() -> datetime:
    return datetime.now(tz=UTC)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def norm_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if len(email) > 320 or not EMAIL_RE.match(email):
        raise ProblemError(422, "Enter a valid email address.", "invalid_email")
    return email


def norm_phone(raw: str) -> str:
    phone = re.sub(r"[\s\-()]", "", raw or "")
    if not PHONE_RE.match(phone):
        raise ProblemError(422, "Enter the phone number with country code, like +919800000000.",
                           "invalid_phone")
    return phone


class AuthProblem(ProblemError):
    def __init__(self, status: int, detail: str, code: str, retry_after: int | None = None) -> None:
        super().__init__(status, detail, code)
        if retry_after:
            self.headers = {"Retry-After": str(retry_after)}


def invalid_code() -> AuthProblem:
    return AuthProblem(400, "That code is wrong or has expired. Request a new one.", "invalid_code")


def invalid_credentials() -> AuthProblem:
    return AuthProblem(401, "Email or password is incorrect.", "invalid_credentials")


@dataclass
class Tokens:
    access_token: str
    expires_in: int
    refresh_token: str
    session_id: uuid.UUID
    user_id: uuid.UUID


@dataclass
class Origin:
    """Where a request came from; recorded on sessions and the audit log."""

    ip: str | None = None
    user_agent: str | None = None


_METERED_AUTH_EVENTS = frozenset({"signin.failed", "signin.blocked", "refresh.reuse_detected",
                                  "otp.rate_limited"})


class AuthService:
    def __init__(self, engine: Engine, cfg: AuthConfig, issuer: Issuer, mailer: Mailer,
                 sms: SmsSender) -> None:
        self.engine, self.cfg, self.issuer, self.mailer, self.sms = engine, cfg, issuer, mailer, sms

    # ------------------------------------------------------------ logging
    def subject_hash(self, value: str) -> str:
        return self.issuer.hmac_hex("subject", value)

    def log(self, action: str, *, user_id: uuid.UUID | None = None, subject: str | None = None,
            ip: str | None = None, meta: dict | None = None) -> None:
        if action in _METERED_AUTH_EVENTS:
            metrics.auth_events.add(1, {"action": action})
        with global_session(self.engine) as db:
            db.add(AuthEvent(action=action, user_id=user_id, ip=ip, meta=meta,
                             subject_hash=self.subject_hash(subject) if subject else None))

    def _count(self, db: Session, action: str, since: datetime, *, subject: str | None = None,
               ip: str | None = None) -> int:
        stmt = select(func.count()).select_from(AuthEvent).where(
            AuthEvent.action == action, AuthEvent.created_at > since)
        if subject is not None:
            stmt = stmt.where(AuthEvent.subject_hash == self.subject_hash(subject))
        if ip is not None:
            stmt = stmt.where(AuthEvent.ip == ip)
        return db.scalar(stmt) or 0

    def _check_failures(self, subject: str, ip: str | None) -> None:
        window = self.cfg.failure_window_seconds
        since = now() - timedelta(seconds=window)
        with global_session(self.engine) as db:
            by_subject = self._count(db, "signin.failed", since, subject=subject)
            by_ip = self._count(db, "signin.failed", since, ip=ip) if ip else 0
        if by_subject >= self.cfg.failures_per_email_window or by_ip >= self.cfg.failures_per_ip_window:
            self.log("signin.blocked", subject=subject, ip=ip)
            raise AuthProblem(429, "Too many attempts. Wait a few minutes and try again.",
                              "rate_limited", retry_after=window)

    def _fail(self, subject: str, ip: str | None, reason: str, user_id=None) -> None:
        self.log("signin.failed", subject=subject, ip=ip, user_id=user_id, meta={"reason": reason})

    # -------------------------------------------------------------- users
    def _user_by_email(self, db: Session, email: str) -> UserAccount | None:
        return db.scalar(select(UserAccount).where(
            UserAccount.issuer == BUILTIN_ISSUER_KEY, func.lower(UserAccount.email) == email,
            UserAccount.deleted_at.is_(None)))

    def _user_by_phone(self, db: Session, phone: str) -> UserAccount | None:
        return db.scalar(select(UserAccount).where(
            UserAccount.issuer == BUILTIN_ISSUER_KEY, UserAccount.phone == phone,
            UserAccount.deleted_at.is_(None)))

    def _create_user(self, db: Session, email: str, name: str | None) -> UserAccount:
        uid = uuid.uuid4()
        user = UserAccount(id=uid, issuer=BUILTIN_ISSUER_KEY, subject=str(uid), email=email,
                           display_name=(name or "").strip()[:200] or None)
        db.add(user)
        db.flush()
        return user

    def create_practice(self, user_id: uuid.UUID, name: str, origin: Origin) -> tuple[uuid.UUID, uuid.UUID]:
        practice_id = uuid.uuid4()
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            bind_practice(db, practice_id)
            db.add(Practice(id=practice_id, name=name.strip()[:200]))
            db.flush()
            member = Member(practice_id=practice_id, user_id=user_id, role=Role.owner)
            db.add(member)
            db.flush()
            db.add(AuditEvent(practice_id=practice_id, actor_user_id=user_id,
                              actor_member_id=member.id, action="practice.created",
                              entity_type="practice", entity_id=str(practice_id), ip=origin.ip))
        return practice_id, member.id

    def memberships(self, user_id: uuid.UUID) -> list[dict]:
        with global_session(self.engine) as db:
            rows = db.execute(text("SELECT * FROM app_memberships(:u)"), {"u": user_id}).mappings()
            return [{"member_id": str(r["member_id"]), "practice_id": str(r["practice_id"]),
                     "practice_name": r["practice_name"], "role": r["role"]} for r in rows]

    def profile(self, user_id: uuid.UUID) -> dict:
        with global_session(self.engine) as db:
            user = db.get(UserAccount, user_id)
            has_pw = db.get(UserCredential, user_id) is not None
            return {"id": str(user_id), "email": user.email, "name": user.display_name,
                    "has_password": has_pw}

    # ------------------------------------------------------------ sessions
    def _start_session(self, db: Session, user: UserAccount, method: str,
                       origin: Origin) -> Tokens:
        sid = uuid.uuid4()
        secret = secrets.token_urlsafe(32)
        t = now()
        db.add(AuthSession(
            id=sid, user_id=user.id, refresh_hash=sha256_hex(secret), method=method,
            ip=origin.ip, user_agent=(origin.user_agent or "")[:300] or None,
            expires_at=t + timedelta(days=self.cfg.refresh_ttl_days),
            absolute_expires_at=t + timedelta(days=self.cfg.refresh_absolute_days)))
        db.flush()
        return Tokens(self.issuer.issue(user.id, sid, user.email, user.display_name),
                      self.cfg.access_ttl_seconds, f"{sid}.{secret}", sid, user.id)

    def refresh(self, token: str, origin: Origin) -> Tokens:
        try:
            sid_raw, secret = token.split(".", 1)
            sid = uuid.UUID(sid_raw)
        except (ValueError, AttributeError):
            raise AuthProblem(401, "Session expired. Sign in again.", "invalid_session") from None
        presented = sha256_hex(secret)
        reuse = False
        with global_session(self.engine) as db:
            s = db.scalar(select(AuthSession).where(AuthSession.id == sid).with_for_update())
            t = now()
            if s is None or s.revoked_at is not None or s.expires_at <= t:
                tokens = None
            elif hmac.compare_digest(presented, s.refresh_hash):
                user = db.get(UserAccount, s.user_id)
                if user is None or user.deleted_at is not None:
                    s.revoked_at, s.revoked_reason, tokens = t, "account", None
                else:
                    new_secret = secrets.token_urlsafe(32)
                    s.prev_refresh_hash, s.refresh_hash = s.refresh_hash, sha256_hex(new_secret)
                    s.last_used_at = t
                    s.expires_at = min(t + timedelta(days=self.cfg.refresh_ttl_days),
                                       s.absolute_expires_at)
                    tokens = Tokens(
                        self.issuer.issue(user.id, s.id, user.email, user.display_name),
                        self.cfg.access_ttl_seconds, f"{s.id}.{new_secret}", s.id, user.id)
            elif s.prev_refresh_hash and hmac.compare_digest(presented, s.prev_refresh_hash):
                # An already-rotated token came back: assume theft, kill the session.
                s.revoked_at, s.revoked_reason, tokens, reuse = t, "reuse", None, True
                uid = s.user_id
            else:
                tokens = None
        if reuse:
            self.log("refresh.reuse_detected", user_id=uid, ip=origin.ip,
                     meta={"session_id": str(sid)})
        if tokens is None:
            raise AuthProblem(401, "Session expired. Sign in again.", "invalid_session")
        return tokens

    def session_active(self, session_id: str) -> bool:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            return False
        with global_session(self.engine) as db:
            row = db.execute(select(AuthSession.revoked_at, AuthSession.absolute_expires_at)
                             .where(AuthSession.id == sid)).first()
        return row is not None and row[0] is None and row[1] > now()

    def revoke_by_refresh(self, token: str, origin: Origin) -> None:
        """Sign out the session the refresh token belongs to. The secret half must match (the
        session id alone, which also appears in access tokens, is not enough)."""
        try:
            sid_raw, secret = token.split(".", 1)
            sid = uuid.UUID(sid_raw)
        except ValueError:
            return
        presented = sha256_hex(secret)
        with global_session(self.engine) as db:
            row = db.execute(select(AuthSession.refresh_hash, AuthSession.prev_refresh_hash)
                             .where(AuthSession.id == sid)).first()
        if row is None or not (
                hmac.compare_digest(presented, row[0])
                or (row[1] and hmac.compare_digest(presented, row[1]))):
            return
        self.revoke_session(None, sid, origin, reason="signout")

    def revoke_session(self, user_id: uuid.UUID | None, sid: uuid.UUID, origin: Origin,
                       reason: str = "revoked") -> bool:
        with global_session(self.engine) as db:
            stmt = update(AuthSession).where(AuthSession.id == sid, AuthSession.revoked_at.is_(None))
            if user_id is not None:
                stmt = stmt.where(AuthSession.user_id == user_id)
            row = db.execute(stmt.values(revoked_at=now(), revoked_reason=reason)
                             .returning(AuthSession.user_id)).first()
        if row:
            self.log("session.revoked", user_id=row[0], ip=origin.ip,
                     meta={"session_id": str(sid), "reason": reason})
        return row is not None

    def revoke_others(self, user_id: uuid.UUID, keep: uuid.UUID | None, origin: Origin) -> int:
        with global_session(self.engine) as db:
            stmt = update(AuthSession).where(
                AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            if keep:
                stmt = stmt.where(AuthSession.id != keep)
            n = db.execute(stmt.values(revoked_at=now(), revoked_reason="revoked")).rowcount
        if n:
            self.log("session.revoked_others", user_id=user_id, ip=origin.ip, meta={"count": n})
        return n

    def list_sessions(self, user_id: uuid.UUID, current: str | None) -> list[dict]:
        with global_session(self.engine) as db:
            rows = db.scalars(select(AuthSession).where(
                AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now()).order_by(AuthSession.last_used_at.desc()))
            return [{"id": str(s.id), "method": s.method, "ip": s.ip, "user_agent": s.user_agent,
                     "created_at": s.created_at.isoformat(),
                     "last_used_at": s.last_used_at.isoformat(), "current": str(s.id) == current}
                    for s in rows]

    def switch_practice(self, user_id: uuid.UUID, session_id: str | None,
                        practice_id: uuid.UUID, origin: Origin) -> dict:
        match = [m for m in self.memberships(user_id) if m["practice_id"] == str(practice_id)]
        if not match:
            raise ProblemError(403, "You are not a member of that practice.", "forbidden")
        if session_id:
            with global_session(self.engine) as db:
                db.execute(update(AuthSession).where(AuthSession.id == uuid.UUID(session_id))
                           .values(practice_id=practice_id))
        self.log("practice.switched", user_id=user_id, ip=origin.ip,
                 meta={"practice_id": str(practice_id)})
        return match[0]

    def session_practice(self, session_id: str) -> uuid.UUID | None:
        with global_session(self.engine) as db:
            return db.scalar(select(AuthSession.practice_id).where(
                AuthSession.id == uuid.UUID(session_id)))

    def finish_signin(self, user_id: uuid.UUID, method: str, origin: Origin) -> Tokens:
        with global_session(self.engine) as db:
            user = db.get(UserAccount, user_id)
            tokens = self._start_session(db, user, method, origin)
        self.log("signin.succeeded", user_id=user_id, ip=origin.ip, meta={"method": method})
        return tokens

    # ---------------------------------------------------------------- OTP
    def _code(self) -> str:
        return f"{secrets.randbelow(10**6):06d}"

    def _code_hash(self, destination: str, code: str) -> str:
        return self.issuer.hmac_hex("otp", f"{destination}:{code}")

    def request_code(self, *, channel: str, destination: str, purpose: str, origin: Origin,
                     meta: dict | None = None) -> None:
        """Always completes silently for unknown accounts (no enumeration).
        Raises only for rate limits and delivery failures."""
        if purpose == "signup" and not self.cfg.signup_enabled:
            raise AuthProblem(403, "Sign-up is closed on this server.", "signup_disabled")
        hour_ago = now() - timedelta(hours=1)
        with global_session(self.engine) as db:
            per_dest = self._count(db, "otp.requested", hour_ago, subject=destination)
            per_ip = self._count(db, "otp.requested", hour_ago, ip=origin.ip) if origin.ip else 0
            # Counted from the event log, which is written for known AND unknown accounts, so
            # the 429 cooldown cannot be used to tell whether an address has an account.
            last = db.scalar(select(func.max(AuthEvent.created_at)).where(
                AuthEvent.action == "otp.requested",
                AuthEvent.subject_hash == self.subject_hash(destination)))
        if per_dest >= self.cfg.otp_requests_per_email_hour or per_ip >= self.cfg.otp_requests_per_ip_hour:
            self.log("otp.rate_limited", subject=destination, ip=origin.ip)
            raise AuthProblem(429, "Too many codes requested. Try again in a while.",
                              "rate_limited", retry_after=3600)
        if last and (now() - last).total_seconds() < self.cfg.otp_resend_seconds:
            raise AuthProblem(429, "A code was just sent. Wait a moment before asking again.",
                              "rate_limited", retry_after=self.cfg.otp_resend_seconds)
        self.log("otp.requested", subject=destination, ip=origin.ip, meta={"purpose": purpose})

        with global_session(self.engine) as db:
            user = (self._user_by_email(db, destination) if channel == "email"
                    else self._user_by_phone(db, destination))
            if purpose == "signin" and user is None:
                return  # silent: same response as success
            if purpose == "signup" and user is not None:
                purpose, meta = "signin", None  # existing account: just sign them in
            db.execute(update(AuthOtp).where(
                AuthOtp.destination == destination, AuthOtp.consumed_at.is_(None))
                .values(consumed_at=now()))
            code = self._code()
            db.add(AuthOtp(channel=channel, destination=destination, purpose=purpose,
                           code_hash=self._code_hash(destination, code),
                           expires_at=now() + timedelta(seconds=self.cfg.otp_ttl_seconds),
                           meta=meta))
        minutes = self.cfg.otp_ttl_seconds // 60
        try:
            if channel == "email":
                self.mailer.send(Message(
                    to=destination, subject=f"Your Ankana sign-in code: {code}",
                    text=(f"Your Ankana sign-in code is {code}\n\nIt expires in {minutes} minutes. "
                          "If you did not ask for it, ignore this message.")))
            else:
                self.sms.send(destination, f"Your Ankana code is {code}. It expires in {minutes} minutes.")
        except MailError:
            self.log("otp.delivery_failed", subject=destination, ip=origin.ip)
            raise AuthProblem(503, "We could not send the code. Try again shortly.",
                              "delivery_failed") from None

    def verify_code(self, *, channel: str, destination: str, code: str, origin: Origin) -> Tokens:
        self._check_failures(destination, origin.ip)
        code = (code or "").strip().replace(" ", "")
        failure: AuthProblem | None = None
        user_id: uuid.UUID | None = None
        purpose = None
        otp_meta: dict | None = None
        with global_session(self.engine) as db:
            otp = db.scalar(select(AuthOtp).where(
                AuthOtp.destination == destination, AuthOtp.consumed_at.is_(None),
                AuthOtp.expires_at > now()).order_by(AuthOtp.created_at.desc()).limit(1))
            if otp is None:
                failure, reason = invalid_code(), "no_code"
            else:
                # Atomic attempt counter: concurrent guesses cannot exceed the cap.
                attempts = db.scalar(
                    update(AuthOtp).where(AuthOtp.id == otp.id, AuthOtp.consumed_at.is_(None),
                                          AuthOtp.attempts < self.cfg.otp_max_attempts)
                    .values(attempts=AuthOtp.attempts + 1).returning(AuthOtp.attempts))
                if attempts is None:
                    failure, reason = invalid_code(), "attempts_exhausted"
                elif not (len(code) == 6 and code.isdigit()) or not hmac.compare_digest(
                        self._code_hash(destination, code), otp.code_hash):
                    failure, reason = invalid_code(), "wrong_code"
                    if attempts >= self.cfg.otp_max_attempts:
                        db.execute(update(AuthOtp).where(AuthOtp.id == otp.id)
                                   .values(consumed_at=now()))
                else:
                    took = db.scalar(update(AuthOtp).where(
                        AuthOtp.id == otp.id, AuthOtp.consumed_at.is_(None))
                        .values(consumed_at=now()).returning(AuthOtp.id))
                    if took is None:
                        failure, reason = invalid_code(), "raced"
                    else:
                        purpose, otp_meta = otp.purpose, otp.meta
        if failure:
            self._fail(destination, origin.ip, reason)
            raise failure

        with global_session(self.engine) as db:
            user = (self._user_by_email(db, destination) if channel == "email"
                    else self._user_by_phone(db, destination))
            if user is None and purpose == "signup" and channel == "email":
                user = self._create_user(db, destination, (otp_meta or {}).get("name"))
                user_id = user.id
                signup_practice = (otp_meta or {}).get("practice_name")
            elif user is None:
                user_id, signup_practice = None, None
            else:
                user_id, signup_practice = user.id, None
        if user_id is None:
            self._fail(destination, origin.ip, "no_user")
            raise invalid_code()
        if signup_practice:
            self.create_practice(user_id, signup_practice, origin)
            self.log("signup.completed", user_id=user_id, ip=origin.ip)
        return self.finish_signin(user_id, "otp", origin)

    # ----------------------------------------------------------- password
    def password_signin(self, email: str, password: str, origin: Origin) -> Tokens:
        if not self.cfg.password_enabled:
            raise AuthProblem(404, "Password sign-in is not enabled.", "password_disabled")
        self._check_failures(email, origin.ip)
        with global_session(self.engine) as db:
            user = self._user_by_email(db, email)
            cred = db.get(UserCredential, user.id) if user else None
            stored = cred.password_hash if cred else DUMMY_HASH
            ok = verify_password(stored, password or "")
            if ok and cred and user and needs_rehash(stored):
                cred.password_hash = hash_password(password)
            uid = user.id if user else None
        if not (ok and cred and uid):
            self._fail(email, origin.ip, "bad_password", user_id=uid)
            raise invalid_credentials()
        return self.finish_signin(uid, "password", origin)

    def set_password(self, user_id: uuid.UUID, new: str, current: str | None,
                     current_session: str | None, origin: Origin) -> None:
        if not self.cfg.password_enabled:
            raise AuthProblem(404, "Password sign-in is not enabled.", "password_disabled")
        with global_session(self.engine) as db:
            user = db.get(UserAccount, user_id)
            email = user.email
            cred = db.get(UserCredential, user_id)
        if cred is not None:
            self._check_failures(email or str(user_id), origin.ip)
            if not verify_password(cred.password_hash, current or ""):
                self._fail(email or str(user_id), origin.ip, "bad_current_password", user_id)
                raise AuthProblem(403, "Your current password is incorrect.", "invalid_credentials")
        try:
            check_policy(new, email=email, min_length=self.cfg.password_min_length,
                         hibp=self.cfg.password_hibp)
        except PasswordPolicyError as exc:
            raise AuthProblem(422, str(exc), "weak_password") from None
        with global_session(self.engine) as db:
            row = db.get(UserCredential, user_id)
            if row is None:
                db.add(UserCredential(user_id=user_id, password_hash=hash_password(new)))
            else:
                row.password_hash = hash_password(new)
        self.log("password.changed" if cred else "password.set", user_id=user_id, ip=origin.ip)
        if cred:  # a changed password signs out every other device
            keep = uuid.UUID(current_session) if current_session else None
            self.revoke_others(user_id, keep, origin)

    # --------------------------------------------------------------- team
    def create_invite(self, *, practice_id: uuid.UUID, inviter_user: uuid.UUID,
                      inviter_member: uuid.UUID, email: str, role: Role,
                      client_id: uuid.UUID | None, origin: Origin) -> dict:
        if role == Role.client and client_id is None:
            raise ProblemError(422, "A client portal invite needs a client_id.", "client_required")
        if role != Role.client and client_id is not None:
            raise ProblemError(422, "client_id is only for the client role.", "client_not_allowed")
        token = secrets.token_urlsafe(32)
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            bind_practice(db, practice_id)
            practice = db.get(Practice, practice_id)
            if client_id is not None and db.scalar(select(Client.id).where(
                    Client.id == client_id, Client.deleted_at.is_(None))) is None:
                raise ProblemError(404, "client not found", "not_found")
            with global_session(self.engine) as g:
                invitee = self._user_by_email(g, email)
                invitee_id = invitee.id if invitee else None
            if invitee_id and db.scalar(select(Member.id).where(
                    Member.user_id == invitee_id, Member.deleted_at.is_(None))):
                raise ProblemError(409, "That person is already a member.", "already_member")
            db.execute(update(PracticeInvite).where(
                PracticeInvite.email == email, PracticeInvite.accepted_at.is_(None),
                PracticeInvite.revoked_at.is_(None)).values(revoked_at=now()))
            invite = PracticeInvite(
                practice_id=practice_id, email=email, role=role, client_id=client_id,
                token_hash=sha256_hex(token), invited_by_member_id=inviter_member,
                expires_at=now() + timedelta(days=self.cfg.invite_ttl_days))
            db.add(invite)
            db.flush()
            db.add(AuditEvent(practice_id=practice_id, actor_user_id=inviter_user,
                              actor_member_id=inviter_member, action="invite.created",
                              entity_type="invite", entity_id=str(invite.id), ip=origin.ip,
                              meta={"role": role.value}))
            practice_name = practice.name
        practice_name = " ".join(practice_name.split())  # no CR/LF in the Subject header
        link = f"{self.cfg.web_base_url}/invite/{token}"
        label = {Role.client: 'a client', Role.owner: 'an owner', Role.astrologer: 'an astrologer',
                 Role.assistant: 'an assistant'}[role]
        try:
            self.mailer.send(Message(
                to=email, subject=f"You are invited to {practice_name} on Ankana",
                text=(f"You have been invited to join {practice_name} on Ankana as {label}."
                      "\n\n"
                      f"Accept the invitation: {link}"
                      "\n\n"
                      f"The link works for {self.cfg.invite_ttl_days} days and only for {email}.")))
        except MailError:
            raise AuthProblem(503, "The invitation was saved but the email could not be sent.",
                              "delivery_failed") from None
        return {"id": str(invite.id), "email": email, "role": role.value,
                "client_id": str(client_id) if client_id else None,
                "expires_at": invite.expires_at.isoformat()}

    def revoke_invite(self, practice_id: uuid.UUID, member, invite_id: uuid.UUID,
                      origin: Origin) -> None:
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            bind_practice(db, practice_id)
            inv = db.get(PracticeInvite, invite_id)
            if inv is None or inv.accepted_at is not None or inv.revoked_at is not None:
                raise ProblemError(404, "invite not found", "not_found")
            inv.revoked_at = now()
            db.add(AuditEvent(practice_id=practice_id, actor_user_id=member.user_id,
                              actor_member_id=member.member_id, action="invite.revoked",
                              entity_type="invite", entity_id=str(invite_id), ip=origin.ip))

    def _lookup_invite(self, token: str) -> dict:
        with global_session(self.engine) as db:
            row = db.execute(text("SELECT * FROM app_invite_lookup(:h)"),
                             {"h": sha256_hex(token)}).mappings().first()
        if row is None:
            raise ProblemError(404, "This invitation link is not valid.", "invite_invalid")
        row = dict(row)
        if row["revoked_at"] or row["accepted_at"] or row["expires_at"] <= now():
            raise ProblemError(410, "This invitation has expired or was already used.",
                               "invite_expired")
        return row

    def preview_invite(self, token: str) -> dict:
        row = self._lookup_invite(token)
        local, _, domain = row["email"].partition("@")
        return {"practice_name": row["practice_name"], "role": row["role"],
                "email_hint": f"{local[:1]}***@{domain}", "email": row["email"]}

    def accept_invite(self, token: str, user_id: uuid.UUID, origin: Origin) -> dict:
        row = self._lookup_invite(token)
        with global_session(self.engine) as db:
            user = db.get(UserAccount, user_id)
            email = (user.email or "").lower()
        if email != row["email"].lower():
            raise ProblemError(403, f"This invitation was sent to {row['email']}. Sign in with "
                               "that address to accept it.", "invite_wrong_user")
        pid = row["practice_id"]
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            bind_practice(db, pid)
            inv = db.scalar(select(PracticeInvite).where(
                PracticeInvite.id == row["invite_id"]).with_for_update())
            if inv.accepted_at is not None or inv.revoked_at is not None:
                raise ProblemError(410, "This invitation was already used.", "invite_expired")
            member = db.scalar(select(Member).where(Member.user_id == user_id))
            if member is not None and member.deleted_at is None:
                raise ProblemError(409, "You are already a member of this practice.",
                                   "already_member")
            if member is None:
                member = Member(practice_id=pid, user_id=user_id, role=inv.role,
                                client_id=inv.client_id)
                db.add(member)
            else:  # re-joining after removal
                member.deleted_at, member.role, member.client_id = None, inv.role, inv.client_id
            db.flush()
            inv.accepted_at = now()
            db.add(AuditEvent(practice_id=pid, actor_user_id=user_id, actor_member_id=member.id,
                              action="invite.accepted", entity_type="invite",
                              entity_id=str(inv.id), ip=origin.ip, meta={"role": inv.role.value}))
            out = {"practice_id": str(pid), "member_id": str(member.id), "role": inv.role.value}
        self.log("invite.accepted", user_id=user_id, ip=origin.ip, meta={"practice_id": str(pid)})
        return out

    def list_invites(self, practice_id: uuid.UUID) -> list[dict]:
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            bind_practice(db, practice_id)
            rows = db.scalars(select(PracticeInvite).where(
                PracticeInvite.accepted_at.is_(None), PracticeInvite.revoked_at.is_(None),
                PracticeInvite.expires_at > now()).order_by(PracticeInvite.created_at.desc()))
            return [{"id": str(i.id), "email": i.email, "role": i.role.value,
                     "client_id": str(i.client_id) if i.client_id else None,
                     "expires_at": i.expires_at.isoformat()} for i in rows]

    def list_members(self, practice_id: uuid.UUID) -> list[dict]:
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            bind_practice(db, practice_id)
            rows = db.execute(
                select(Member, UserAccount).join(UserAccount, UserAccount.id == Member.user_id)
                .where(Member.deleted_at.is_(None)).order_by(Member.created_at))
            return [{"member_id": str(m.id), "user_id": str(u.id), "email": u.email,
                     "name": u.display_name, "role": m.role.value,
                     "client_id": str(m.client_id) if m.client_id else None} for m, u in rows]

    def _owners(self, db: Session) -> int:
        return db.scalar(select(func.count()).select_from(Member).where(
            Member.role == Role.owner, Member.deleted_at.is_(None))) or 0

    def change_role(self, practice_id: uuid.UUID, actor, member_id: uuid.UUID, role: Role,
                    origin: Origin) -> dict:
        if role not in STAFF_ROLES:
            raise ProblemError(422, "Members can be owner, astrologer or assistant.", "invalid_role")
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            bind_practice(db, practice_id)
            m = db.scalar(select(Member).where(Member.id == member_id, Member.deleted_at.is_(None))
                          .with_for_update())
            if m is None:
                raise ProblemError(404, "member not found", "not_found")
            if m.role == Role.client:
                raise ProblemError(422, "Client portal access is managed through invites.",
                                   "invalid_role")
            if m.role == Role.owner and role != Role.owner and self._owners(db) <= 1:
                raise ProblemError(409, "A practice needs at least one owner.", "last_owner")
            before, m.role = m.role, role
            db.add(AuditEvent(practice_id=practice_id, actor_user_id=actor.user_id,
                              actor_member_id=actor.member_id, action="member.role_changed",
                              entity_type="member", entity_id=str(member_id), ip=origin.ip,
                              meta={"from": before.value, "to": role.value}))
        return {"member_id": str(member_id), "role": role.value}

    def remove_member(self, practice_id: uuid.UUID, actor, member_id: uuid.UUID,
                      origin: Origin) -> None:
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            bind_practice(db, practice_id)
            m = db.scalar(select(Member).where(Member.id == member_id, Member.deleted_at.is_(None))
                          .with_for_update())
            if m is None:
                raise ProblemError(404, "member not found", "not_found")
            if m.role == Role.owner and self._owners(db) <= 1:
                raise ProblemError(409, "A practice needs at least one owner.", "last_owner")
            m.deleted_at = now()
            db.add(AuditEvent(practice_id=practice_id, actor_user_id=actor.user_id,
                              actor_member_id=actor.member_id, action="member.removed",
                              entity_type="member", entity_id=str(member_id), ip=origin.ip))

    # --------------------------------------------------------------- OIDC
    def link_oidc_user(self, provider: str, subject: str, email: str, name: str | None,
                       origin: Origin) -> uuid.UUID:
        """Find or create the Ankana user for a verified external identity."""
        with global_session(self.engine) as db:
            ident = db.scalar(select(AuthIdentity).where(
                AuthIdentity.provider == provider, AuthIdentity.subject == subject))
            if ident is not None:
                user = db.get(UserAccount, ident.user_id)
                if user is None or user.deleted_at is not None:
                    raise AuthProblem(403, "This account is disabled.", "account_disabled")
                return user.id
            user = self._user_by_email(db, email)
            created = False
            if user is None:
                if not self.cfg.signup_enabled:
                    raise AuthProblem(403, "Sign-up is closed on this server.", "signup_disabled")
                user, created = self._create_user(db, email, name), True
            db.add(AuthIdentity(user_id=user.id, provider=provider, subject=subject, email=email))
            uid = user.id
        self.log("identity.linked", user_id=uid, ip=origin.ip,
                 meta={"provider": provider, "created_user": created})
        return uid
