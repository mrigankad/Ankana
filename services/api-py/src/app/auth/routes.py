"""HTTP surface of the built-in auth: /v1/auth/*, team routes and /.well-known.

Transports. Browsers get the refresh token as an httpOnly cookie (path
/v1/auth, SameSite=Lax) and the access token in the JSON body, held in memory
by the web app. Non-browser clients send `X-Auth-Transport: body` and receive
the refresh token in the body instead; with no ambient cookie there is nothing
for CSRF to ride on.

CSRF for the cookie endpoints (refresh, signout): the request must carry an
Origin from AUTH_ALLOWED_ORIGINS and the custom header `X-Ankana-Csrf: 1`
(forces a CORS preflight that only allowed origins pass), on top of SameSite.
"""

from __future__ import annotations

import hmac
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.tenancy.models import Role
from app.v1.common import ProblemError

from .deps import CurrentMember, current_principal, current_user_id, require_roles
from .mailer import sms_enabled
from .oidc import OidcClient, OidcError
from .service import (
    AuthProblem,
    AuthService,
    Origin,
    Tokens,
    norm_email,
    norm_phone,
    sha256_hex,
)
from .verifier import Principal

CSRF_HEADER = "x-ankana-csrf"
OIDC_STATE_COOKIE = "ankana_oidc"


# --------------------------------------------------------------- plumbing
def svc(request: Request) -> AuthService:
    return request.app.state.auth


def origin_of(request: Request) -> Origin:
    cfg = request.app.state.auth.cfg
    ip = request.client.host if request.client else None
    fwd = request.headers.get("x-forwarded-for")
    if cfg.trust_proxy and fwd:
        ip = fwd.split(",")[-1].strip() or ip
    return Origin(ip=ip, user_agent=request.headers.get("user-agent"))


def check_origin(request: Request, *, strict: bool) -> None:
    cfg = request.app.state.auth.cfg
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin and origin not in cfg.allowed_origins:
        raise ProblemError(403, "Cross-site request refused.", "csrf_origin")
    if strict:
        if not origin:
            raise ProblemError(403, "Cross-site request refused.", "csrf_origin")
        if request.headers.get(CSRF_HEADER) != "1":
            raise ProblemError(403, "Missing CSRF header.", "csrf_header")


def body_transport(request: Request) -> bool:
    return request.headers.get("x-auth-transport", "").lower() == "body"


def set_refresh_cookie(request: Request, response: Response, token: str) -> None:
    cfg = svc(request).cfg
    response.set_cookie(
        cfg.cookie_name, token, max_age=cfg.refresh_ttl_days * 86400, httponly=True,
        secure=cfg.cookie_secure, samesite="lax", path="/v1/auth", domain=cfg.cookie_domain)


def clear_refresh_cookie(request: Request, response: Response) -> None:
    cfg = svc(request).cfg
    response.delete_cookie(cfg.cookie_name, path="/v1/auth", domain=cfg.cookie_domain,
                           secure=cfg.cookie_secure, httponly=True, samesite="lax")


def session_payload(service: AuthService, tokens: Tokens, include_refresh: bool) -> dict:
    memberships = service.memberships(tokens.user_id)
    active = service.session_practice(str(tokens.session_id))
    if active is None and len(memberships) == 1:
        active = uuid.UUID(memberships[0]["practice_id"])
    body = {
        "access_token": tokens.access_token, "token_type": "Bearer",
        "expires_in": tokens.expires_in, "session_id": str(tokens.session_id),
        "user": service.profile(tokens.user_id), "memberships": memberships,
        "active_practice_id": str(active) if active else None,
    }
    if include_refresh:
        body["refresh_token"] = tokens.refresh_token
    return body


def respond(request: Request, tokens: Tokens) -> JSONResponse:
    service = svc(request)
    as_body = body_transport(request)
    response = JSONResponse(session_payload(service, tokens, include_refresh=as_body),
                            headers={"Cache-Control": "no-store"})
    if not as_body:
        set_refresh_cookie(request, response, tokens.refresh_token)
    return response


# ---------------------------------------------------------------- models
class EmailIn(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)


class SignupIn(BaseModel):
    email: str = Field(max_length=320)
    name: str = Field(min_length=1, max_length=200)
    # Omitted when the person is joining an existing practice through an invite.
    practice_name: str | None = Field(default=None, min_length=1, max_length=200)


class VerifyIn(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    code: str = Field(max_length=12)


class PasswordSigninIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)


class PasswordSetIn(BaseModel):
    new_password: str = Field(max_length=256)
    current_password: str | None = Field(default=None, max_length=256)


class RefreshIn(BaseModel):
    refresh_token: str | None = None


class SwitchIn(BaseModel):
    practice_id: uuid.UUID


class PracticeCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class InviteIn(BaseModel):
    email: str = Field(max_length=320)
    role: Role
    client_id: uuid.UUID | None = None


class RoleIn(BaseModel):
    role: Role


def _channel(email: str | None, phone: str | None) -> tuple[str, str]:
    if email:
        return "email", norm_email(email)
    if phone:
        return "phone", norm_phone(phone)
    raise ProblemError(422, "Provide an email address or a phone number.", "destination_required")


# ----------------------------------------------------------------- router
def build_auth_router() -> APIRouter:
    r = APIRouter(prefix="/v1/auth", tags=["auth"])

    @r.get("/config", operation_id="getAuthConfig", summary="Which sign-in methods are on")
    def auth_config(request: Request) -> dict:
        cfg = svc(request).cfg
        return {"email_code": True, "phone_code": sms_enabled(cfg),
                "password": cfg.password_enabled, "signup": cfg.signup_enabled,
                "oidc": [{"id": p.id, "label": p.label} for p in cfg.oidc],
                "password_min_length": cfg.password_min_length,
                "otp_ttl_seconds": cfg.otp_ttl_seconds}

    @r.post("/signup", status_code=202, operation_id="authSignup",
            summary="Start sign-up: emails a code that creates the account and practice")
    def signup(body: SignupIn, request: Request) -> dict:
        check_origin(request, strict=False)
        service = svc(request)
        email = norm_email(body.email)
        service.request_code(channel="email", destination=email, purpose="signup",
                             origin=origin_of(request),
                             meta={"name": body.name.strip(),
                                   "practice_name": (body.practice_name or "").strip() or None})
        return {"ok": True, "expires_in": service.cfg.otp_ttl_seconds}

    @r.post("/otp/request", status_code=202, operation_id="authRequestCode",
            summary="Email (or SMS) a one-time sign-in code")
    def otp_request(body: EmailIn, request: Request) -> dict:
        check_origin(request, strict=False)
        service = svc(request)
        channel, destination = _channel(body.email, body.phone)
        service.request_code(channel=channel, destination=destination, purpose="signin",
                             origin=origin_of(request))
        return {"ok": True, "expires_in": service.cfg.otp_ttl_seconds}

    @r.post("/otp/verify", operation_id="authVerifyCode",
            summary="Exchange a one-time code for a session")
    def otp_verify(body: VerifyIn, request: Request) -> Response:
        check_origin(request, strict=False)
        channel, destination = _channel(body.email, body.phone)
        tokens = svc(request).verify_code(channel=channel, destination=destination,
                                          code=body.code, origin=origin_of(request))
        return respond(request, tokens)

    @r.post("/password/signin", operation_id="authPasswordSignin",
            summary="Email and password sign-in")
    def password_signin(body: PasswordSigninIn, request: Request) -> Response:
        check_origin(request, strict=False)
        tokens = svc(request).password_signin(norm_email(body.email), body.password,
                                              origin_of(request))
        return respond(request, tokens)

    @r.put("/password", status_code=204, operation_id="authSetPassword",
           summary="Set or change the password (changing signs out other devices)")
    def set_password(body: PasswordSetIn, request: Request,
                     principal: Principal = Depends(current_principal),
                     user_id: uuid.UUID = Depends(current_user_id)) -> Response:
        svc(request).set_password(user_id, body.new_password, body.current_password,
                                  principal.session_id, origin_of(request))
        return Response(status_code=204)

    @r.post("/refresh", operation_id="authRefresh",
            summary="Rotate the refresh token and mint a new access token")
    def refresh(request: Request, body: RefreshIn | None = None) -> Response:
        service = svc(request)
        token = body.refresh_token if body and body.refresh_token else None
        from_cookie = token is None
        if from_cookie:
            token = request.cookies.get(service.cfg.cookie_name)
            check_origin(request, strict=True)
        else:
            check_origin(request, strict=False)
        if not token:
            raise AuthProblem(401, "Not signed in.", "invalid_session")
        try:
            tokens = service.refresh(token, origin_of(request))
        except AuthProblem:
            if from_cookie:
                resp = JSONResponse(
                    {"type": "https://ankana.app/problems/invalid_session", "title": "Unauthorized",
                     "status": 401, "detail": "Session expired. Sign in again.",
                     "code": "invalid_session"}, status_code=401,
                    media_type="application/problem+json")
                clear_refresh_cookie(request, resp)
                return resp
            raise
        resp = JSONResponse(session_payload(service, tokens, include_refresh=not from_cookie),
                            headers={"Cache-Control": "no-store"})
        if from_cookie:
            set_refresh_cookie(request, resp, tokens.refresh_token)
        return resp

    @r.post("/signout", status_code=204, operation_id="authSignout",
            summary="Revoke the current session")
    def signout(request: Request, body: RefreshIn | None = None) -> Response:
        service = svc(request)
        token = body.refresh_token if body and body.refresh_token else None
        from_cookie = token is None
        if from_cookie:
            token = request.cookies.get(service.cfg.cookie_name)
            check_origin(request, strict=True)
        if token:
            service.revoke_by_refresh(token, origin_of(request))
        resp = Response(status_code=204)
        clear_refresh_cookie(request, resp)
        return resp

    @r.get("/session", operation_id="authSession",
           summary="Who am I: profile, memberships and the active practice")
    def session(request: Request, principal: Principal = Depends(current_principal),
                user_id: uuid.UUID = Depends(current_user_id)) -> dict:
        service = svc(request)
        memberships = service.memberships(user_id)
        active = service.session_practice(principal.session_id) if principal.session_id else None
        if active is None and len(memberships) == 1:
            active = uuid.UUID(memberships[0]["practice_id"])
        return {"user": service.profile(user_id), "memberships": memberships,
                "active_practice_id": str(active) if active else None,
                "session_id": principal.session_id}

    @r.get("/sessions", operation_id="authListSessions", summary="Signed-in devices")
    def sessions(request: Request, principal: Principal = Depends(current_principal),
                 user_id: uuid.UUID = Depends(current_user_id)) -> dict:
        return {"sessions": svc(request).list_sessions(user_id, principal.session_id)}

    @r.delete("/sessions/{session_id}", status_code=204, operation_id="authRevokeSession",
              summary="Sign out one device")
    def revoke(session_id: uuid.UUID, request: Request,
               user_id: uuid.UUID = Depends(current_user_id)) -> Response:
        if not svc(request).revoke_session(user_id, session_id, origin_of(request)):
            raise ProblemError(404, "session not found", "not_found")
        return Response(status_code=204)

    @r.delete("/sessions", operation_id="authRevokeOtherSessions",
              summary="Sign out every other device")
    def revoke_others(request: Request, principal: Principal = Depends(current_principal),
                      user_id: uuid.UUID = Depends(current_user_id)) -> dict:
        keep = uuid.UUID(principal.session_id) if principal.session_id else None
        return {"revoked": svc(request).revoke_others(user_id, keep, origin_of(request))}

    @r.post("/practices", status_code=201, operation_id="authCreatePractice",
            summary="Create a practice for the signed-in user (they become owner)")
    def create_practice(body: PracticeCreateIn, request: Request,
                        principal: Principal = Depends(current_principal),
                        user_id: uuid.UUID = Depends(current_user_id)) -> dict:
        service = svc(request)
        if not service.cfg.signup_enabled:
            raise AuthProblem(403, "Creating practices is closed on this server.", "signup_disabled")
        pid, mid = service.create_practice(user_id, body.name, origin_of(request))
        if principal.session_id:
            service.switch_practice(user_id, principal.session_id, pid, origin_of(request))
        return {"practice_id": str(pid), "member_id": str(mid), "role": "owner"}

    @r.post("/switch-practice", operation_id="authSwitchPractice",
            summary="Make a practice the default for this session")
    def switch(body: SwitchIn, request: Request,
               principal: Principal = Depends(current_principal),
               user_id: uuid.UUID = Depends(current_user_id)) -> dict:
        m = svc(request).switch_practice(user_id, principal.session_id, body.practice_id,
                                         origin_of(request))
        return {"practice_id": m["practice_id"], "role": m["role"],
                "practice_name": m["practice_name"]}

    # ----------------------------------------------------------- invites
    @r.get("/invites/{token}", operation_id="authPreviewInvite",
           summary="What an invitation link is for (public, token is the secret)")
    def preview_invite(token: str, request: Request) -> dict:
        return svc(request).preview_invite(token)

    @r.post("/invites/{token}/accept", operation_id="authAcceptInvite",
            summary="Accept an invitation as the signed-in user (email must match)")
    def accept_invite(token: str, request: Request,
                      principal: Principal = Depends(current_principal),
                      user_id: uuid.UUID = Depends(current_user_id)) -> dict:
        service = svc(request)
        out = service.accept_invite(token, user_id, origin_of(request))
        if principal.session_id:
            service.switch_practice(user_id, principal.session_id,
                                    uuid.UUID(out["practice_id"]), origin_of(request))
        return out

    # -------------------------------------------------------------- OIDC
    def web_redirect(request: Request, path: str) -> RedirectResponse:
        return RedirectResponse(svc(request).cfg.web_base_url + path, status_code=302)

    def oidc(request: Request) -> OidcClient:
        return request.app.state.oidc

    @r.get("/oidc/{provider}/start", operation_id="authOidcStart", include_in_schema=False)
    def oidc_start(provider: str, request: Request, redirect: str | None = None) -> Response:
        p = svc(request).cfg.oidc_provider(provider)
        if p is None:
            raise ProblemError(404, "unknown provider", "not_found")
        if redirect and (not redirect.startswith("/") or redirect.startswith(("//", "/\\"))
                         or any(ord(ch) < 32 or ch == "\\" for ch in redirect)):
            redirect = None  # relative paths only: no open redirect (browsers read /\ as //)
        try:
            url, state = oidc(request).start(p, redirect)
        except OidcError:
            return web_redirect(request, "/sign-in?error=oidc_unavailable")
        resp = RedirectResponse(url, status_code=302)
        cfg = svc(request).cfg
        resp.set_cookie(OIDC_STATE_COOKIE, sha256_hex(state), max_age=600, httponly=True,
                        secure=cfg.cookie_secure, samesite="lax", path="/v1/auth",
                        domain=cfg.cookie_domain)
        return resp

    @r.get("/oidc/callback", operation_id="authOidcCallback", include_in_schema=False)
    def oidc_callback(request: Request, code: str | None = None, state: str | None = None,
                      error: str | None = None) -> Response:
        if error or not code or not state:
            return web_redirect(request, "/sign-in?error=oidc_denied")
        service = svc(request)
        bound = request.cookies.get(OIDC_STATE_COOKIE) or ""
        if not hmac.compare_digest(bound, sha256_hex(state)):
            # The browser that finishes the flow is not the one that started it.
            resp = web_redirect(request, "/sign-in?error=oidc_state_invalid")
            resp.delete_cookie(OIDC_STATE_COOKIE, path="/v1/auth", domain=service.cfg.cookie_domain)
            return resp
        try:
            uid, redirect_to, _ = oidc(request).finish(code, state, origin_of(request))
        except AuthProblem as exc:
            return web_redirect(request, f"/sign-in?error={exc.code}")
        tokens = service.finish_signin(uid, "oidc", origin_of(request))
        resp = web_redirect(request, "/auth/callback?next=" + quote(redirect_to or "/"))
        set_refresh_cookie(request, resp, tokens.refresh_token)
        resp.delete_cookie(OIDC_STATE_COOKIE, path="/v1/auth", domain=service.cfg.cookie_domain)
        return resp

    return r


def build_team_router() -> APIRouter:
    """Owner-only team management, under /v1/practice."""
    r = APIRouter(prefix="/v1/practice", tags=["team"])
    owner = require_roles(Role.owner)

    @r.post("/invites", status_code=201, operation_id="createInvite",
            summary="Invite a teammate or a client-portal user by email")
    def create_invite(body: InviteIn, request: Request, me: CurrentMember = Depends(owner)) -> dict:
        return svc(request).create_invite(
            practice_id=me.practice_id, inviter_user=me.user_id, inviter_member=me.member_id,
            email=norm_email(body.email), role=body.role, client_id=body.client_id,
            origin=origin_of(request))

    @r.get("/invites", operation_id="listInvites", summary="Pending invitations")
    def list_invites(request: Request, me: CurrentMember = Depends(owner)) -> dict:
        return {"invites": svc(request).list_invites(me.practice_id)}

    @r.delete("/invites/{invite_id}", status_code=204, operation_id="revokeInvite")
    def revoke_invite(invite_id: uuid.UUID, request: Request,
                      me: CurrentMember = Depends(owner)) -> Response:
        svc(request).revoke_invite(me.practice_id, me, invite_id, origin_of(request))
        return Response(status_code=204)

    @r.get("/members", operation_id="listMembers", summary="Team and portal users")
    def list_members(request: Request, me: CurrentMember = Depends(owner)) -> dict:
        return {"members": svc(request).list_members(me.practice_id)}

    @r.patch("/members/{member_id}", operation_id="changeMemberRole")
    def change_role(member_id: uuid.UUID, body: RoleIn, request: Request,
                    me: CurrentMember = Depends(owner)) -> dict:
        return svc(request).change_role(me.practice_id, me, member_id, body.role,
                                        origin_of(request))

    @r.delete("/members/{member_id}", status_code=204, operation_id="removeMember")
    def remove_member(member_id: uuid.UUID, request: Request,
                      me: CurrentMember = Depends(owner)) -> Response:
        svc(request).remove_member(me.practice_id, me, member_id, origin_of(request))
        return Response(status_code=204)

    return r


def build_wellknown_router() -> APIRouter:
    r = APIRouter(tags=["auth"], include_in_schema=False)

    @r.get("/.well-known/jwks.json")
    def jwks(request: Request) -> JSONResponse:
        return JSONResponse(svc(request).issuer.jwks(),
                            headers={"Cache-Control": "public, max-age=300"})

    @r.get("/.well-known/openid-configuration")
    def discovery(request: Request) -> JSONResponse:
        return JSONResponse(svc(request).issuer.discovery(),
                            headers={"Cache-Control": "public, max-age=300"})

    return r
