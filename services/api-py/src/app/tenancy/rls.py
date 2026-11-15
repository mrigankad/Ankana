"""Row-level security SQL, shared by the Alembic migration and tests.

Model: every request runs in one transaction that starts with
`SELECT set_config('app.practice_id', <uuid>, true)` (the SET LOCAL
equivalent that accepts bind parameters). Policies compare practice_id to that
setting. When the setting is absent or empty, nullif() yields NULL, the
comparison is NULL and no row is visible or writable (fail closed).

The app connects as a non-owner, non-superuser role (APP_ROLE). Superusers
and BYPASSRLS roles ignore RLS, so production must never use one for the API.
FORCE ROW LEVEL SECURITY also binds the table owner.
"""

from .models import TENANT_TABLES

APP_ROLE = "ankana_app"

CURRENT_PRACTICE = "nullif(current_setting('app.practice_id', true), '')::uuid"


def enable_rls_sql(tables: tuple[str, ...] = TENANT_TABLES,
                   append_only: tuple[str, ...] = ("audit_event",)) -> list[str]:
    stmts: list[str] = []
    for table in tables:
        stmts.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        stmts.append(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        if table in append_only:
            # Append-only: no UPDATE or DELETE policy exists, so both are denied.
            stmts.append(
                f"CREATE POLICY tenant_select ON {table} FOR SELECT "
                f"USING (practice_id = {CURRENT_PRACTICE})"
            )
            stmts.append(
                f"CREATE POLICY tenant_insert ON {table} FOR INSERT "
                f"WITH CHECK (practice_id = {CURRENT_PRACTICE})"
            )
        else:
            stmts.append(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING (practice_id = {CURRENT_PRACTICE}) "
                f"WITH CHECK (practice_id = {CURRENT_PRACTICE})"
            )
    # The tenant root keys on its own id.
    stmts += [
        "ALTER TABLE practice ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE practice FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY tenant_isolation ON practice "
        f"USING (id = {CURRENT_PRACTICE}) WITH CHECK (id = {CURRENT_PRACTICE})",
    ]
    return stmts


def drop_rls_sql(tables: tuple[str, ...] = TENANT_TABLES) -> list[str]:
    stmts = []
    for table in (*tables, "practice"):
        stmts.append(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        stmts.append(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    return stmts


# Cross-tenant lookup needed before a practice is chosen (login, practice
# picker). SECURITY DEFINER runs as the owner and FORCE RLS still applies to
# the owner, so the function disables row security for itself.
MEMBERSHIPS_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION app_memberships(p_user_id uuid)
RETURNS TABLE (member_id uuid, practice_id uuid, role text, practice_name text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp SET row_security = off AS $$
    SELECT m.id, m.practice_id, m.role, p.name
    FROM member m JOIN practice p ON p.id = m.practice_id
    WHERE m.user_id = p_user_id AND m.deleted_at IS NULL AND p.deleted_at IS NULL
$$
"""


def grants_sql(tables: tuple[str, ...] = TENANT_TABLES) -> list[str]:
    stmts = [
        f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}",
        f"GRANT SELECT, INSERT, UPDATE ON user_account TO {APP_ROLE}",
    ]
    for table in (*tables, "practice"):
        if table == "audit_event":
            stmts.append(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}")
        else:
            stmts.append(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")
    stmts.append("REVOKE ALL ON FUNCTION app_memberships(uuid) FROM PUBLIC")
    stmts.append(f"GRANT EXECUTE ON FUNCTION app_memberships(uuid) TO {APP_ROLE}")
    return stmts
