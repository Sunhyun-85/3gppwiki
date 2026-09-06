from __future__ import annotations

import argparse
import contextlib
import fcntl
import io
import json
import logging
import shutil
import sys
import time
from datetime import UTC, datetime
from dataclasses import replace
from pathlib import Path

from ran2wiki.config import Config, load_config
from ran2wiki.db import connect, initialize
from ran2wiki.search import KnowledgeService
from ran2wiki.indexing import extract_pending, index_extracted
from ran2wiki.sync.client import RepositoryClient
from ran2wiki.sync.engine import SyncSummary, select_meetings_for_update, sync_entries
from ran2wiki.groups import get_group_adapter, supported_groups
from ran2wiki.models import meeting_sort_key

LOG = logging.getLogger("ran2wiki")


def _config(args: argparse.Namespace) -> Config:
    return load_config(args.config)


def cmd_init(args: argparse.Namespace) -> int:
    config_file = Path(args.config)
    if not config_file.exists() and Path("config.example.yaml").exists():
        shutil.copyfile("config.example.yaml", config_file)
        print(f"Created {config_file}")
    config = load_config(config_file)
    for directory in (config.paths.data_dir / "raw", config.paths.data_dir / "extracted", config.paths.database.parent):
        directory.mkdir(parents=True, exist_ok=True)
    with initialize(config.paths.database):
        pass
    print(f"Initialized RAN2 Wiki database at {config.paths.database}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = _config(args)
    if not config.paths.database.exists():
        print("RAN2 Wiki is not initialized. Run: ran2wiki init")
        return 1
    with initialize(config.paths.database) as db:
        if getattr(args, "json", False):
            service = KnowledgeService(db)
            groups = {}
            for adapter in supported_groups():
                repository = config.repositories.get(adapter.name)
                enabled = repository.enabled if repository else adapter.name == "RAN2"
                groups[adapter.name] = {"enabled": enabled, **service.status(adapter.name)}
            _emit({"schema_version": 1, "database_path": str(config.paths.database),
                   "database_size_bytes": config.paths.database.stat().st_size, "groups": groups})
            return 0
        counts = {
            "Meetings indexed": db.execute("SELECT count(*) FROM meetings").fetchone()[0],
            "TDocs indexed": db.execute("SELECT count(*) FROM tdocs").fetchone()[0],
            "Rel-20 relevant TDocs": db.execute("SELECT count(*) FROM tdocs WHERE classification IN ('REL20','REL20_AND_6G')").fetchone()[0],
            "6G relevant TDocs": db.execute("SELECT count(*) FROM tdocs WHERE classification IN ('6G','REL20_AND_6G')").fetchone()[0],
            "Chair Note sections": db.execute("SELECT count(*) FROM chair_note_sections").fetchone()[0],
        }
        latest = db.execute("SELECT name FROM meetings ORDER BY number DESC, suffix DESC LIMIT 1").fetchone()
        last_sync = db.execute("SELECT finished_at FROM sync_runs WHERE status='success' ORDER BY id DESC LIMIT 1").fetchone()
        current_sync = db.execute("""
          SELECT status,discovered_count,downloaded_count,changed_count,error
          FROM sync_runs ORDER BY id DESC LIMIT 1
        """).fetchone()
    print("RAN2 Wiki Status\n")
    for name, value in counts.items():
        print(f"{name}: {value}")
    print(f"Latest meeting: {latest[0] if latest else '-'}")
    print(f"Last successful sync: {last_sync[0] if last_sync else '-'}")
    if current_sync:
        print(f"Current/last sync state: {current_sync['status']} "
              f"(discovered={current_sync['discovered_count']}, "
              f"downloaded={current_sync['downloaded_count']}, changed={current_sync['changed_count']})")
        if current_sync["error"]:
            print(f"Last sync error: {current_sync['error']}")
    print(f"Database size: {config.paths.database.stat().st_size:,} bytes")
    return 0


def cmd_pending(args: argparse.Namespace) -> int:
    print(f"'{args.command}' is planned for the next implementation phase and is not falsely reported as operational.")
    return 2


def _meeting_name(value: str, group: str = "RAN2") -> str:
    return get_group_adapter(group).meeting_name(value)


def _group(args: argparse.Namespace) -> str:
    group = getattr(args, "group", "RAN2").upper()
    get_group_adapter(group)
    return group


def _group_config(config: Config, group: str) -> Config:
    repository = config.repositories.get(group)
    if group == "RAN2" and repository is None:
        return config
    if repository is None or not repository.enabled or not repository.base_url:
        raise ValueError(f"{group} is disabled or has no inspected repository configuration")
    return replace(
        config,
        scope=replace(config.scope, group=group,
                      start_meeting=repository.start_meeting or config.scope.start_meeting,
                      end_meeting=repository.end_meeting),
        source=replace(config.source, base_url=repository.base_url,
                       download_base_url=repository.download_base_url or repository.base_url),
    )


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def cmd_sync(args: argparse.Namespace) -> int:
    config = _config(args)
    group = _group(args)
    config = _group_config(config, group)
    initialize(config.paths.database).close()
    meeting = _meeting_name(args.value or config.scope.start_meeting, group)
    meeting_url = f"{config.source.base_url.rstrip('/')}/{meeting}/"
    client = RepositoryClient(config.source.timeout_seconds)
    with connect(config.paths.database) as db:
        run_id = db.execute("INSERT INTO sync_runs(group_name,status) VALUES (?,'running') RETURNING id", (group,)).fetchone()[0]
        db.commit()
        try:
            entries = client.walk_primary_files(meeting_url)
            summary = sync_entries(db, config.paths.data_dir, meeting, meeting_url, entries, client.fetch,
                                   config.source.download_workers, group)
            db.execute("""UPDATE sync_runs SET finished_at=?,status='success',discovered_count=?,downloaded_count=?,changed_count=? WHERE id=?""",
                       (datetime.now(UTC).isoformat(), summary.discovered, summary.downloaded, summary.changed, run_id))
            db.commit()
        except Exception as exc:
            db.execute("UPDATE sync_runs SET finished_at=?,status='failed',error=? WHERE id=?",
                       (datetime.now(UTC).isoformat(), str(exc), run_id))
            db.commit()
            LOG.error("sync failed for %s: %s", meeting, exc)
            return 1
        finally:
            client.close()
    print(f"{meeting}: discovered={summary.discovered} downloaded={summary.downloaded} changed={summary.changed} unchanged={summary.unchanged}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    config = _config(args)
    with initialize(config.paths.database) as db:
        success, failed = extract_pending(db, config)
    print(f"Extracted: {success}; failed: {failed}")
    return 1 if failed else 0


def cmd_index(args: argparse.Namespace) -> int:
    config = _config(args)
    with initialize(config.paths.database) as db:
        result = index_extracted(db, config)
    print(f"TDoc rows processed: {result['tdocs']}; FTS rows: {result['fts_rows']}; "
          f"document chunks: {result['document_chunks']}; Chair sections: {result['chair_sections']}; "
          f"outcomes: {result['chair_outcomes']}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    if getattr(args, "meeting", None):
        args.value = args.meeting
    if getattr(args, "json", False):
        return _cmd_update_json(args)
    return _run_update_locked(args)


def _run_update_locked(args: argparse.Namespace) -> int:
    config = _config(args)
    if config.paths.database.exists():
        with connect(config.paths.database) as db:
            active = db.execute(
                "SELECT id,started_at FROM sync_runs WHERE status='running' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if active:
            print(f"Another ranwiki update is already running (sync run {active['id']}, started {active['started_at']}).")
            return 3
    lock_path = config.paths.data_dir / ".ranwiki-update.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another ranwiki update is already running.")
            return 3
        return _run_update(args)


def _run_update(args: argparse.Namespace) -> int:
    sync_code = 0
    if args.value:
        sync_code = cmd_sync(args)
    else:
        sync_code = cmd_sync_range(args)
    # A remote failure must not strand files already downloaded by this run.
    # Extraction/indexing is deterministic and operates only on complete local files.
    extract_code = cmd_extract(args)
    index_code = cmd_index(args)
    return max(sync_code, extract_code, index_code)


def cmd_sync_range(args: argparse.Namespace) -> int:
    """Discover configured meetings, ingest all new ones, and recheck recent ones."""
    config = _config(args)
    group = _group(args)
    config = _group_config(config, group)
    initialize(config.paths.database).close()
    client = RepositoryClient(config.source.timeout_seconds)
    total = SyncSummary()
    with connect(config.paths.database) as db:
        now = datetime.now(UTC).isoformat()
        db.execute("""
          UPDATE sync_runs SET finished_at=?,status='failed',
          error=coalesce(error,'interrupted before completion') WHERE status='running'
        """, (now,))
        run_id = db.execute("INSERT INTO sync_runs(group_name,status) VALUES (?,'running') RETURNING id", (group,)).fetchone()[0]
        db.commit()
        try:
            remote = client.discover_meetings(
                config.source.base_url, config.scope.start_meeting, config.scope.end_meeting, group
            )
            known = {row[0] for row in db.execute("SELECT name FROM meetings")}
            layout_current = db.execute(
                "SELECT value FROM app_state WHERE key='storage_layout'"
            ).fetchone()
            # The first v2 run corrects every old flat source path once.
            legacy = known if not layout_current or layout_current[0] != "v2" else set()
            selected = select_meetings_for_update(
                remote, known - legacy, config.source.recent_meetings_to_recheck
            )
            LOG.info(
                "repository has %d in-scope meetings; updating %d (%d new)",
                len(remote), len(selected), sum(item.name not in known for item in selected),
            )
            for meeting in selected:
                entries = client.walk_primary_files(meeting.url)
                if not entries:
                    LOG.info("skipping empty/planned meeting directory %s", meeting.name)
                    continue
                summary = sync_entries(
                    db, config.paths.data_dir, meeting.name, meeting.url, entries, client.fetch,
                    config.source.download_workers, group,
                )
                total += summary
                db.execute("""
                  UPDATE sync_runs SET discovered_count=?,downloaded_count=?,changed_count=? WHERE id=?
                """, (total.discovered, total.downloaded, total.changed, run_id))
                db.commit()
                print(
                    f"{meeting.name}: discovered={summary.discovered} "
                    f"downloaded={summary.downloaded} changed={summary.changed} "
                    f"unchanged={summary.unchanged}"
                )
            db.execute("""
              UPDATE sync_runs SET finished_at=?,status='success',discovered_count=?,
              downloaded_count=?,changed_count=? WHERE id=?
            """, (datetime.now(UTC).isoformat(), total.discovered, total.downloaded,
                  total.changed, run_id))
            db.execute("""
              INSERT INTO app_state(key,value) VALUES ('storage_layout','v2')
              ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """)
            db.commit()
        except Exception as exc:
            db.execute(
                "UPDATE sync_runs SET finished_at=?,status='failed',error=? WHERE id=?",
                (datetime.now(UTC).isoformat(), str(exc), run_id),
            )
            db.commit()
            LOG.error("incremental update discovery/sync failed: %s", exc)
            return 1
        finally:
            client.close()
    print(
        f"Update sync total: discovered={total.discovered} downloaded={total.downloaded} "
        f"changed={total.changed} unchanged={total.unchanged}"
    )
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    config = _config(args)
    if not config.paths.database.exists():
        print("RAN2 Wiki is not initialized. Run: ran2wiki init")
        return 1
    group = getattr(args, "group", "RAN2").upper()
    get_group_adapter(group)
    with initialize(config.paths.database) as db:
        service = KnowledgeService(db)
        if args.command == "audit":
            value = service.audit(group, args.limit)
        elif args.command == "search":
            value = service.search_ran2(args.value, args.scope, args.meeting, args.from_meeting,
                                        args.to_meeting, args.agenda, args.company, args.limit,
                                        group, args.release)
        elif args.command == "trace":
            value = service.trace_topic(args.value, group=group, scope=args.scope)
        elif args.command == "meeting":
            value = service.get_meeting(args.value, group)
        elif args.command == "chair-notes":
            value = service.get_chair_notes(args.value, args.agenda, group, args.limit)
        elif args.command == "outcomes":
            types = [item.strip().upper() for item in args.types.split(",") if item.strip()]
            allowed = {"AGREEMENT", "CONCLUSION", "FFS", "POSTPONED", "NOTED"}
            invalid = set(types) - allowed
            if invalid:
                raise ValueError(f"invalid outcome type(s): {', '.join(sorted(invalid))}")
            rows = []
            for kind in types or ["AGREEMENT", "CONCLUSION", "FFS"]:
                rows.extend(service.find_agreements(args.value, kind, args.limit, group))
            value = sorted(rows, key=lambda row: meeting_sort_key(row["meeting"]))[:args.limit]
        else:
            value = service.get_tdoc(args.value, group)
            if value and not args.full:
                text = value.pop("full_text", "") or ""
                value["content_excerpt"] = text[:args.max_chars]
                value["content_truncated"] = len(text) > args.max_chars
    if getattr(args, "json", False):
        key = "results" if isinstance(value, list) else "result"
        envelope = {"schema_version": 1, "command": args.command, "group": group,
                    key: value}
        if hasattr(args, "value"):
            envelope["query" if args.command in {"search", "trace", "outcomes"} else "id"] = args.value
        _emit(envelope)
    else:
        _emit(value)
    return 0 if value else 1


def _cmd_update_json(args: argparse.Namespace) -> int:
    config = _config(args)
    group = _group(args)
    with initialize(config.paths.database) as db:
        before_meetings = {row[0] for row in db.execute("SELECT name FROM meetings WHERE group_name=?", (group,))}
        before_docs = db.execute("SELECT count(*) FROM documents").fetchone()[0]
        before_tdocs = db.execute("SELECT count(*) FROM tdocs").fetchone()[0]
    started = time.monotonic()
    capture = io.StringIO()
    clone = argparse.Namespace(**vars(args)); clone.json = False
    with contextlib.redirect_stdout(capture):
        code = _run_update_locked(clone)
    with connect(config.paths.database) as db:
        after_meetings = {row[0] for row in db.execute("SELECT name FROM meetings WHERE group_name=?", (group,))}
        after_docs = db.execute("SELECT count(*) FROM documents").fetchone()[0]
        after_tdocs = db.execute("SELECT count(*) FROM tdocs").fetchone()[0]
        run = db.execute("SELECT * FROM sync_runs WHERE group_name=? ORDER BY id DESC LIMIT 1", (group,)).fetchone()
    report = dict(run) if run else {}
    error = report.get("error")
    _emit({"schema_version": 1, "command": "update", "group": group,
           "status": "success" if code == 0 else "failed",
           "meetings_discovered": sorted(after_meetings - before_meetings, key=meeting_sort_key),
           "files_checked": report.get("discovered_count", 0),
           "files_downloaded": report.get("downloaded_count", 0),
           "files_changed": report.get("changed_count", 0),
           "documents_extracted": max(0, after_docs - before_docs),
           "records_indexed": max(0, after_tdocs - before_tdocs),
           "errors": [error] if error else [],
           "warnings": [line for line in capture.getvalue().splitlines()
                        if line.startswith("Another ranwiki update")],
           "elapsed_seconds": round(time.monotonic() - started, 3)})
    return code


def cmd_serve(args: argparse.Namespace) -> int:
    from ran2wiki.mcp.server import main as serve
    serve()
    return 0


def cmd_serve_web(args: argparse.Namespace) -> int:
    from ran2wiki.web.server import main as serve
    serve()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ranwiki" if Path(sys.argv[0]).name == "ranwiki" else "ran2wiki")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)
    for name, func in (("update", cmd_update), ("sync", cmd_sync)):
        item = sub.add_parser(name)
        item.add_argument("value", nargs="?", help="meeting number/suffix, e.g. 131bis")
        item.add_argument("--group", default="RAN2", choices=("RAN2", "RAN3", "RAN4"))
        item.add_argument("--json", action="store_true")
        if name == "update":
            item.add_argument("--meeting", help="update only this meeting number/name")
            item.add_argument("--all-enabled", action="store_true",
                              help="update every enabled group (currently RAN2)")
        item.set_defaults(func=func)
    sub.add_parser("extract").set_defaults(func=cmd_extract)
    sub.add_parser("index").set_defaults(func=cmd_index)
    for name in ("search", "trace", "meeting", "tdoc", "chair-notes", "outcomes", "audit"):
        item = sub.add_parser(name)
        if name != "audit":
            item.add_argument("value")
        item.add_argument("--limit", type=int, default=100 if name == "chair-notes" else 20)
        item.add_argument("--group", default="RAN2", choices=("RAN2", "RAN3", "RAN4"))
        item.add_argument("--json", action="store_true")
        if name in {"search", "trace"}:
            item.add_argument("--scope", default="ALL", type=str.upper, choices=("REL20", "6G", "ALL"))
        if name == "search":
            item.add_argument("--meeting")
            item.add_argument("--from-meeting")
            item.add_argument("--to-meeting")
            item.add_argument("--agenda")
            item.add_argument("--company")
            item.add_argument("--release")
        if name == "chair-notes":
            item.add_argument("--agenda")
        if name == "outcomes":
            item.add_argument("--types", default="AGREEMENT,CONCLUSION,FFS")
        if name == "tdoc":
            item.add_argument("--full", action="store_true")
            item.add_argument("--max-chars", type=int, default=6000)
        item.set_defaults(func=cmd_lookup)
    sub.add_parser("serve-mcp").set_defaults(func=cmd_serve)
    sub.add_parser("serve-web").set_defaults(func=cmd_serve_web)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    if not args.verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
