"""SQL for the auth migration, kept next to the code that depends on it."""

from app.tenancy.rls import APP_ROLE

# Invitee has no practice context yet, so the token lookup is a SECURITY
# DEFINER function (same pattern as app_memberships). It returns one row at
# most and exposes nothing but the invite and the practice name.
INVITE_LOOKUP_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION app_invite_lookup(p_token_hash text)
RETURNS TABLE (invite_id uuid, practice_id uuid, practice_name text, email text, role text,
               client_id uuid, expires_at timestamptz, accepted_at timestamptz,
               revoked_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp SET row_security = off AS $$
    SELECT i.id, i.practice_id, p.name, i.email, i.role, i.client_id, i.expires_at,
           i.accepted_at, i.revoked_at
    FROM practice_invite i JOIN practice p ON p.id = i.practice_id
    WHERE i.token_hash = p_token_hash AND p.deleted_at IS NULL
$$
"""

GLOBAL_GRANTS = {
    "user_credential": "SELECT, INSERT, UPDATE",
    "auth_identity": "SELECT, INSERT, UPDATE, DELETE",
    "auth_otp": "SELECT, INSERT, UPDATE, DELETE",
    "auth_session": "SELECT, INSERT, UPDATE",
    "auth_oidc_state": "SELECT, INSERT, DELETE",
    "auth_event": "SELECT, INSERT",  # append-only
}


def grants_sql() -> list[str]:
    stmts = [f"GRANT {privs} ON {table} TO {APP_ROLE}" for table, privs in GLOBAL_GRANTS.items()]
    stmts.append("REVOKE ALL ON FUNCTION app_invite_lookup(text) FROM PUBLIC")
    stmts.append(f"GRANT EXECUTE ON FUNCTION app_invite_lookup(text) TO {APP_ROLE}")
    return stmts
