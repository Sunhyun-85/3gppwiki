from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote, urlsplit

from ran2wiki.models import FileKind, RemoteEntry, meeting_sort_key

LOG = logging.getLogger(__name__)
Fetch = Callable[[str], bytes]


@dataclass(frozen=True)
class SyncSummary:
    discovered: int = 0
    downloaded: int = 0
    changed: int = 0
    unchanged: int = 0

    def __add__(self, other: "SyncSummary") -> "SyncSummary":
        return SyncSummary(*(getattr(self, field) + getattr(other, field)
                             for field in ("discovered", "downloaded", "changed", "unchanged")))


def select_meetings_for_update(remote: Iterable[RemoteEntry], known: set[str],
                               recent_count: int) -> list[RemoteEntry]:
    """Return every new meeting plus the newest configured meetings for rechecking."""
    ordered = sorted(remote, key=lambda item: meeting_sort_key(item.name))
    recent_names = {item.name for item in ordered[-max(0, recent_count):]} if recent_count else set()
    return [item for item in ordered if item.name not in known or item.name in recent_names]


def _meeting_parts(name: str) -> tuple[int, str]:
    number, _, normalized = meeting_sort_key(name)
    suffix = normalized.removeprefix(str(number))
    return number, suffix


def _category(kind: FileKind) -> str:
    return {
        FileKind.CHAIR_NOTES: "chair_notes", FileKind.AGENDA: "agenda",
        FileKind.TDOC_LIST: "tdoc_lists", FileKind.TDOC: "tdocs",
        FileKind.REPORT: "reports",
    }.get(kind, "metadata")


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ #+-]", "_", Path(name).name)


def _destination(data_dir: Path, meeting_name: str, entry: RemoteEntry) -> Path:
    """Mirror the official path below each category so Docs/Inbox never collide."""
    parts = [unquote(part) for part in urlsplit(entry.url).path.split("/") if part]
    try:
        meeting_index = next(i for i, part in enumerate(parts) if part.casefold() == meeting_name.casefold())
        relative = parts[meeting_index + 1:]
    except StopIteration:
        relative = [entry.name]
    safe_parts = [_safe_name(part) for part in relative] or [_safe_name(entry.name)]
    return data_dir / "raw" / meeting_name / _category(entry.kind) / Path(*safe_parts)


def sync_entries(db: sqlite3.Connection, data_dir: Path, meeting_name: str, meeting_url: str,
                 entries: Iterable[RemoteEntry], fetch: Fetch, workers: int = 1,
                 group: str = "RAN2") -> SyncSummary:
    """Synchronize one already-discovered meeting; suitable for live and fixture clients."""
    now = datetime.now(UTC).isoformat()
    number, suffix = _meeting_parts(meeting_name)
    db.execute("""
      INSERT INTO meetings(name,number,suffix,source_url,last_checked,group_name) VALUES (?,?,?,?,?,?)
      ON CONFLICT(name) DO UPDATE SET source_url=excluded.source_url,last_checked=excluded.last_checked,
      group_name=excluded.group_name
    """, (meeting_name, number, suffix, meeting_url, now, group))
    meeting_id = db.execute("SELECT id FROM meetings WHERE name=?", (meeting_name,)).fetchone()[0]
    db.commit()
    counts = {"discovered": 0, "downloaded": 0, "changed": 0, "unchanged": 0}
    pending: list[tuple[RemoteEntry, sqlite3.Row | None, Path, bytes | None]] = []
    for entry in entries:
        if entry.is_directory:
            continue
        counts["discovered"] += 1
        existing = db.execute("SELECT * FROM files WHERE source_url=?", (entry.url,)).fetchone()
        local_exists = bool(existing and existing["local_path"] and Path(existing["local_path"]).exists())
        remote_modified = entry.modified_at.isoformat() if entry.modified_at else None
        # Listing sizes are sometimes rounded (KB/MB), while we retain exact bytes.
        # A stable modification timestamp is therefore the strongest cheap signal.
        metadata_unchanged = (
            existing and remote_modified and existing["remote_modified"] == remote_modified
        ) or (
            existing and not remote_modified and existing["remote_modified"] is None
            and existing["size"] == entry.size
        )
        same_metadata = bool(existing and local_exists and metadata_unchanged)
        if same_metadata:
            db.execute("UPDATE files SET last_checked=? WHERE id=?", (now, existing["id"]))
            counts["unchanged"] += 1
            continue
        destination = _destination(data_dir, meeting_name, entry)
        # Adopt a file left by an interrupted run instead of downloading it again.
        recovered = destination.read_bytes() if existing is None and destination.is_file() else None
        pending.append((entry, existing, destination, recovered))
    db.commit()

    def persist(entry: RemoteEntry, existing: sqlite3.Row | None,
                destination: Path, payload: bytes) -> None:
        digest = hashlib.sha256(payload).hexdigest()
        existing_local = bool(existing and existing["local_path"] and Path(existing["local_path"]).exists())
        remote_modified = entry.modified_at.isoformat() if entry.modified_at else None
        if existing and existing["sha256"] == digest and existing_local:
            db.execute("UPDATE files SET size=?,remote_modified=?,last_checked=? WHERE id=?",
                       (entry.size, entry.modified_at.isoformat() if entry.modified_at else None, now, existing["id"]))
            counts["unchanged"] += 1
            db.commit()
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and existing and existing["sha256"]:
            versioned = destination.with_name(f"{destination.name}.{existing['sha256'][:12]}.previous")
            if not versioned.exists():
                os.replace(destination, versioned)
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
        first = existing["first_downloaded"] if existing else now
        db.execute("""
          INSERT INTO files(meeting_id,kind,filename,source_url,size,remote_modified,sha256,first_downloaded,last_checked,local_path,extraction_status)
          VALUES (?,?,?,?,?,?,?,?,?,?, 'pending')
          ON CONFLICT(source_url) DO UPDATE SET meeting_id=excluded.meeting_id,kind=excluded.kind,
          filename=excluded.filename,size=excluded.size,remote_modified=excluded.remote_modified,
          sha256=excluded.sha256,last_checked=excluded.last_checked,local_path=excluded.local_path,extraction_status='pending'
        """, (meeting_id, entry.kind.value, entry.name, entry.url, len(payload),
              entry.modified_at.isoformat() if entry.modified_at else None, digest, first, now, str(destination)))
        file_id = db.execute("SELECT id FROM files WHERE source_url=?", (entry.url,)).fetchone()[0]
        db.execute("INSERT OR IGNORE INTO file_versions(file_id,sha256,size,remote_modified,local_path) VALUES (?,?,?,?,?)",
                   (file_id, digest, len(payload), entry.modified_at.isoformat() if entry.modified_at else None, str(destination)))
        counts["downloaded"] += 1
        if existing:
            counts["changed"] += 1
        db.commit()

    recovered_items = [item for item in pending if item[3] is not None]
    download_items = [item for item in pending if item[3] is None]
    for entry, existing, destination, payload in recovered_items:
        persist(entry, existing, destination, payload or b"")

    worker_count = max(1, min(workers, 16))
    # Bound completed payloads in memory by submitting a few worker-sized batches.
    batch_size = worker_count * 3
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="ran2-download") as pool:
        for offset in range(0, len(download_items), batch_size):
            batch = download_items[offset:offset + batch_size]
            futures = {
                pool.submit(fetch, entry.url): (entry, existing, destination)
                for entry, existing, destination, _ in batch
            }
            for future in as_completed(futures):
                entry, existing, destination = futures[future]
                persist(entry, existing, destination, future.result())
    return SyncSummary(**counts)
