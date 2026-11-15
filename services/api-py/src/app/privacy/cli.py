"""Operator commands: python -m app.privacy.cli <command>

Connection: API_MIGRATION_URL (owner) or API_DATABASE_URL (app role) are both fine;
every statement binds app.practice_id, so RLS stays on.

  rotate-master        re-wrap all practice keys under the current master key
                       (set ANKANA_MASTER_KEY/_ID, keep old ones in ANKANA_MASTER_KEY_PREVIOUS)
  rotate-data          new data key version + re-encrypt (--practice ID | --all) [--purge-retired]
  rotate-ai-keys       re-encrypt ai_connection.api_key_enc: ANKANA_SECRET_KEY_OLD -> ANKANA_SECRET_KEY
  backfill             encrypt any plaintext values and rebuild blind indexes
  retention-sweep      queue retention_apply for practices with auto-apply on
  purge-exports        delete expired export ZIPs
  replay-erasures      after a database restore: re-apply every erasure logged since --since
                       (--source storage|db|<events.jsonl>, --dry-run); exit 1 on any failure
  export-erasure-log   dump the erasure events since --since to a JSONL file (--out), e.g. from
                       the live server just before a restore
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from sqlalchemy import create_engine, text

from . import backfill, crypto


def _engine():
    url = os.getenv("API_MIGRATION_URL") or os.getenv("API_DATABASE_URL")
    if not url:
        raise SystemExit("set API_MIGRATION_URL or API_DATABASE_URL")
    return create_engine(url, future=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.privacy.cli", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rotate-master")
    rd = sub.add_parser("rotate-data")
    rd.add_argument("--practice")
    rd.add_argument("--all", action="store_true")
    rd.add_argument("--purge-retired", action="store_true")
    sub.add_parser("rotate-ai-keys")
    sub.add_parser("backfill")
    sub.add_parser("retention-sweep")
    sub.add_parser("purge-exports")
    rp = sub.add_parser("replay-erasures")
    rp.add_argument("--since", required=True, help="ISO 8601 time of the restore point (UTC if no zone)")
    rp.add_argument("--source", default="storage", help="storage (default), db, or a .jsonl file")
    rp.add_argument("--dry-run", action="store_true")
    ep = sub.add_parser("export-erasure-log")
    ep.add_argument("--since", required=True)
    ep.add_argument("--out", required=True)
    args = p.parse_args(argv)
    engine = _engine()

    if args.cmd == "rotate-master":
        with engine.begin() as conn:
            print(f"re-wrapped {backfill.rotate_master(conn)} keys")
    elif args.cmd == "rotate-data":
        if not (args.practice or args.all):
            raise SystemExit("pass --practice ID or --all")
        with engine.begin() as conn:
            ids = [args.practice] if args.practice else backfill.practice_ids(conn)
        for pid in ids:
            with engine.begin() as conn:
                print(backfill.rotate_data_key(conn, pid))
        if args.purge_retired:
            time.sleep(crypto.KEY_TTL_SECONDS + 5)  # let other processes drop the old key
            for pid in ids:
                with engine.begin() as conn:
                    print(f"{pid}: purged {backfill.purge_retired(conn, pid)} retired keys")
    elif args.cmd == "rotate-ai-keys":
        new, old = os.getenv("ANKANA_SECRET_KEY"), os.getenv("ANKANA_SECRET_KEY_OLD")
        if not (new and old):
            raise SystemExit("set ANKANA_SECRET_KEY (new) and ANKANA_SECRET_KEY_OLD")
        with engine.begin() as conn:
            print(f"re-encrypted {backfill.rotate_ai_keys(conn, new, old)} API keys")
    elif args.cmd == "backfill":
        with engine.begin() as conn:
            print(f"encrypted {backfill.encrypt_existing(conn)} values")
    elif args.cmd == "retention-sweep":
        from app.tenancy.session import tenant_session

        from . import service

        with engine.connect() as conn:
            todo = [(str(r[0])) for r in conn.execute(text(
                "SELECT practice_id FROM privacy_practices() "
                "WHERE retention_inactive_years IS NOT NULL AND retention_auto_apply"))]
        for pid in todo:
            with tenant_session(engine, pid) as db:
                service.create_request(db, practice_id=pid, kind="retention_apply")
        print(f"queued retention for {len(todo)} practices")
    elif args.cmd == "purge-exports":
        from app.storage import storage_from_env
        from app.tenancy.session import tenant_session

        from . import service

        storage = storage_from_env()
        with engine.connect() as conn:
            ids = backfill.practice_ids(conn)
        total = 0
        for pid in ids:
            with tenant_session(engine, pid) as db:
                total += service.purge_expired_exports(db, storage)
        print(f"purged {total} expired exports")
    elif args.cmd in ("replay-erasures", "export-erasure-log"):
        return _erasure_commands(args, engine)
    return 0


def _parse_since(value: str):
    from datetime import UTC, datetime

    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(f"--since must be an ISO 8601 timestamp, got {value!r}") from None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _erasure_commands(args, engine) -> int:
    import json

    from . import erasure_log

    since = _parse_since(args.since)
    if args.cmd == "export-erasure-log":
        events = erasure_log.read_db(engine, since)
        print(f"wrote {erasure_log.write_file(args.out, events)} events to {args.out}")
        return 0
    from app.storage import storage_from_env

    storage = storage_from_env()
    if args.source == "storage":
        events = erasure_log.read_storage(storage, since)
    elif args.source == "db":
        events = erasure_log.read_db(engine, since)
    else:
        events = erasure_log.read_file(args.source, since)
    result = erasure_log.replay(engine, storage, events, dry_run=args.dry_run)
    print(json.dumps({"since": since.isoformat(), "events": len(events), **result}))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
