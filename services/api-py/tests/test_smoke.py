def test_imports() -> None:
    import astronomy  # noqa: F401

    import nakshatra_core  # noqa: F401


def test_alembic_has_a_single_head_and_a_linear_chain() -> None:
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert len(script.get_heads()) == 1, script.get_heads()
    assert all(len(rev.nextrev) <= 1 for rev in script.walk_revisions()), "branching history"
