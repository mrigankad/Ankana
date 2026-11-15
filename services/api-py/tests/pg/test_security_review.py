"""Security review regressions that need a real Postgres (docs/security-review.md)."""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg

# Global tables by design (no practice column, or reached only through the auth service).
GLOBAL_TABLES = {
    "alembic_version", "user_account", "user_credential", "auth_identity", "auth_otp",
    "auth_session", "auth_oidc_state", "auth_event", "job",
    # Shared rate limit counters, keyed by a hash of scope and caller; no personal data.
    "rate_limit_bucket",
    # Payment webhook ledger: events arrive before the practice is known; ids only.
    "billing_event",
    # Gapless GST invoice counter per financial year, shared by all practices by law.
    "invoice_sequence",
}


def test_every_practice_scoped_table_has_forced_rls_and_a_policy(owner_engine) -> None:
    """Any table with a practice_id column (or the practice root) must force RLS and have a
    policy, so a future migration that forgets RLS fails here."""
    with owner_engine.connect() as c:
        rows = c.execute(text("""
            SELECT cl.relname, cl.relrowsecurity, cl.relforcerowsecurity,
                   (SELECT count(*) FROM pg_policy p WHERE p.polrelid = cl.oid) AS policies,
                   EXISTS (SELECT 1 FROM information_schema.columns col
                           WHERE col.table_schema = 'public' AND col.table_name = cl.relname
                             AND col.column_name = 'practice_id') AS has_practice
            FROM pg_class cl JOIN pg_namespace n ON n.oid = cl.relnamespace
            WHERE n.nspname = 'public' AND cl.relkind = 'r'""")).all()
    unscoped = []
    for name, rls, forced, policies, has_practice in rows:
        if name in GLOBAL_TABLES:
            continue
        if not (has_practice or name == "practice"):
            unscoped.append(name)
            continue
        assert rls and forced and policies >= 1, f"{name}: RLS={rls} FORCE={forced} policies={policies}"
    assert not unscoped, f"tables with no practice_id and not declared global: {unscoped}"


def test_security_definer_functions_pin_search_path_without_temp_first(owner_engine) -> None:
    with owner_engine.connect() as c:
        rows = c.execute(text("""
            SELECT p.proname, p.proconfig FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.prosecdef""")).all()
    assert {r[0] for r in rows} >= {"app_memberships", "app_invite_lookup"}
    for name, cfg in rows:
        flat = ";".join(cfg or [])
        assert "search_path=public, pg_temp" in flat, f"{name}: {flat}"
        assert "row_security=off" in flat


def test_app_role_cannot_create_in_public_or_bypass_rls(owner_engine) -> None:
    with owner_engine.connect() as c:
        row = c.execute(text(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'ankana_app'")).one()
    assert row == (False, False)
