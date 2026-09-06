from __future__ import annotations

import logging
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from ran2wiki.classification import classify_text
from ran2wiki.config import Config
from ran2wiki.parsers.chair_notes import ChairSection, parse_docx
from ran2wiki.parsers.extract import extract_document, write_extracted
from ran2wiki.parsers.tdoc_list import parse_workbook

LOG = logging.getLogger(__name__)
SUPPORTED = {".docx", ".pptx", ".xlsx", ".xlsm", ".pdf", ".txt", ".zip"}


def _json_path(config: Config, meeting: str, file_id: int, filename: str) -> Path:
    # A TDoc can exist in both Docs and Inbox with the same basename.
    # File IDs keep extracted representations distinct and stably traceable.
    return config.paths.data_dir / "extracted" / meeting / f"{file_id}-{filename}.json"


def extract_pending(db: sqlite3.Connection, config: Config) -> tuple[int, int]:
    success = failed = 0
    rows = db.execute("""SELECT f.*,m.name meeting FROM files f LEFT JOIN meetings m ON m.id=f.meeting_id
                         WHERE f.extraction_status IN ('pending','failed') AND f.local_path IS NOT NULL""").fetchall()
    for position, row in enumerate(rows, 1):
        source = Path(row["local_path"])
        if source.suffix.lower() not in SUPPORTED:
            db.execute("UPDATE files SET extraction_status='unsupported' WHERE id=?", (row["id"],))
            if position % 25 == 0:
                db.commit()
            continue
        try:
            result = extract_document(source)
            destination = _json_path(config, row["meeting"] or "unknown", row["id"], row["filename"])
            write_extracted(result, destination)
            db.execute("""INSERT INTO documents(file_id,title,full_text,structured_json_path,extractor_version)
              VALUES (?,?,?,?,?) ON CONFLICT(file_id) DO UPDATE SET title=excluded.title,full_text=excluded.full_text,
              structured_json_path=excluded.structured_json_path,extractor_version=excluded.extractor_version""",
                       (row["id"], row["filename"], result["text"], str(destination), "0.1"))
            db.execute("UPDATE files SET extraction_status='extracted' WHERE id=?", (row["id"],))
            success += 1
        except Exception as exc:
            LOG.exception("extraction failed for %s", source)
            db.execute("UPDATE files SET extraction_status='failed' WHERE id=?", (row["id"],))
            failed += 1
        if position % 25 == 0:
            db.commit()
        if position % 250 == 0:
            LOG.info("extraction progress: %d/%d files", position, len(rows))
    db.commit()
    return success, failed


def _index_tdoc_lists(db: sqlite3.Connection, config: Config) -> int:
    count = 0
    rows = db.execute("SELECT f.*,m.name meeting FROM files f JOIN meetings m ON m.id=f.meeting_id WHERE f.kind='tdoc_list' AND f.local_path IS NOT NULL").fetchall()
    for row in rows:
        try:
            parsed = parse_workbook(row["local_path"])
        except Exception:
            LOG.exception("TDoc list parse failed for %s", row["local_path"])
            continue
        for item in parsed:
            agenda_id = None
            if item.agenda:
                db.execute("INSERT OR IGNORE INTO agenda_items(meeting_id,number,title) VALUES (?,?,NULL)", (row["meeting_id"], item.agenda))
                agenda_id = db.execute("SELECT id FROM agenda_items WHERE meeting_id=? AND number=?", (row["meeting_id"], item.agenda)).fetchone()[0]
            classification = classify_text(" ".join(x or "" for x in (item.title, item.comments)), item.work_item, config.classification).value
            tdoc_file = db.execute("SELECT id FROM files WHERE meeting_id=? AND upper(filename) LIKE ? ORDER BY id LIMIT 1",
                                   (row["meeting_id"], f"{item.tdoc_id.upper()}%" )).fetchone()
            db.execute("""INSERT INTO tdocs(tdoc_id,meeting_id,title,source_company,agenda_item_id,work_item,status,revision_of,comments,file_id,classification)
              VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tdoc_id) DO UPDATE SET meeting_id=excluded.meeting_id,title=excluded.title,
              source_company=excluded.source_company,agenda_item_id=excluded.agenda_item_id,work_item=excluded.work_item,
              status=excluded.status,revision_of=excluded.revision_of,comments=excluded.comments,file_id=coalesce(excluded.file_id,tdocs.file_id),
              classification=excluded.classification""",
                       (item.tdoc_id,row["meeting_id"],item.title,item.source_company,agenda_id,item.work_item,item.status,
                        item.revision,item.comments,tdoc_file[0] if tdoc_file else row["id"],classification))
            count += 1
    return count


def _chair_score(filename: str) -> tuple[int, int, str]:
    lower = filename.casefold()
    primary = 3 if "chairnotes" in lower or "chair_notes" in lower else 0
    final = 3 if "final" in lower else 2 if "eom" in lower else 0
    return primary + final, final, lower


def _parse_chair_source(path: Path) -> list[ChairSection]:
    if path.suffix.casefold() == ".docx":
        return parse_docx(path)
    if path.suffix.casefold() != ".zip":
        return []
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix="ran2wiki-chair-") as temporary:
        candidates = [item for item in archive.infolist() if not item.is_dir() and
                      item.filename.casefold().endswith(".docx") and ".." not in Path(item.filename).parts]
        if not candidates:
            return []
        selected = max(candidates, key=lambda item: _chair_score(item.filename))
        destination = Path(temporary) / Path(selected.filename).name
        with archive.open(selected) as incoming, destination.open("wb") as outgoing:
            while chunk := incoming.read(1024 * 1024):
                outgoing.write(chunk)
        return parse_docx(destination)


def _index_chair_notes(db: sqlite3.Connection) -> tuple[int, int]:
    sections_count = outcomes_count = 0
    meetings = db.execute("SELECT id,name FROM meetings").fetchall()
    for meeting in meetings:
        candidates = db.execute("SELECT * FROM files WHERE meeting_id=? AND kind='chair_notes' AND local_path IS NOT NULL",
                                (meeting["id"],)).fetchall()
        if not candidates:
            continue
        # One canonical main Chair Notes version prevents interim agreements from
        # being duplicated or superseded material from being presented as final.
        selected = max(candidates, key=lambda row: _chair_score(row["filename"]))
        try:
            parsed = _parse_chair_source(Path(selected["local_path"]))
        except Exception:
            LOG.exception("Chair Notes parse failed for %s", selected["local_path"])
            continue
        db.execute("DELETE FROM chair_note_sections WHERE meeting_id=?", (meeting["id"],))
        for ordinal, section in enumerate(parsed, 1):
            db.execute("""INSERT INTO agenda_items(meeting_id,number,title) VALUES (?,?,?)
              ON CONFLICT(meeting_id,number) DO UPDATE SET title=CASE WHEN excluded.title!='' THEN excluded.title ELSE agenda_items.title END""",
                       (meeting["id"], section.agenda, section.title))
            agenda_id = db.execute("SELECT id FROM agenda_items WHERE meeting_id=? AND number=?",
                                   (meeting["id"], section.agenda)).fetchone()[0]
            section_id = db.execute("""INSERT INTO chair_note_sections(meeting_id,file_id,agenda_item_id,ordinal,title,discussion,locator)
              VALUES (?,?,?,?,?,?,?) RETURNING id""",
                                    (meeting["id"], selected["id"], agenda_id, ordinal, section.title,
                                     "\n".join(section.discussion), section.locator)).fetchone()[0]
            for outcome in section.outcomes:
                db.execute("INSERT INTO chair_note_outcomes(section_id,outcome_type,text,locator) VALUES (?,?,?,?)",
                           (section_id, outcome.outcome_type, outcome.text, outcome.locator))
                outcomes_count += 1
            for tdoc_id in section.tdoc_ids:
                tdoc = db.execute("SELECT id FROM tdocs WHERE tdoc_id=?", (tdoc_id,)).fetchone()
                if tdoc:
                    db.execute("INSERT OR IGNORE INTO chair_section_tdocs(section_id,tdoc_id) VALUES (?,?)", (section_id, tdoc[0]))
            sections_count += 1
    return sections_count, outcomes_count


def _index_document_chunks(db: sqlite3.Connection) -> int:
    """Materialize extractor blocks with their locators for provenance-aware retrieval."""
    count = 0
    rows = db.execute("SELECT id,structured_json_path FROM documents WHERE structured_json_path IS NOT NULL").fetchall()
    for row in rows:
        path = Path(row["structured_json_path"])
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            LOG.exception("structured extraction JSON could not be read: %s", path)
            continue
        db.execute("DELETE FROM document_chunks WHERE document_id=?", (row["id"],))
        for ordinal, block in enumerate(payload.get("blocks", []), 1):
            text = str(block.get("text") or "").strip()
            if not text:
                continue
            locator = block.get("locator") or f"block:{ordinal}"
            section = block.get("member") or block.get("type")
            db.execute("""INSERT INTO document_chunks(document_id,ordinal,section,locator,text)
              VALUES (?,?,?,?,?)""", (row["id"], ordinal, section, str(locator), text))
            count += 1
    return count


def index_extracted(db: sqlite3.Connection, config: Config) -> dict[str, int]:
    tdocs = _index_tdoc_lists(db, config)
    chair_sections, chair_outcomes = _index_chair_notes(db)
    chunks = _index_document_chunks(db)
    # Link extracted document records to TDocs after list metadata created them.
    db.execute("""UPDATE documents SET tdoc_id=(SELECT t.id FROM tdocs t JOIN files f ON f.id=documents.file_id
      WHERE upper(f.filename) LIKE t.tdoc_id || '%' LIMIT 1) WHERE tdoc_id IS NULL""")
    db.execute("DELETE FROM tdocs_fts")
    db.execute("""INSERT INTO tdocs_fts(tdoc_id,title,body)
      SELECT t.tdoc_id,coalesce(t.title,''),coalesce(d.full_text,'') FROM tdocs t LEFT JOIN documents d ON d.tdoc_id=t.id""")
    db.execute("DELETE FROM chair_notes_fts")
    db.execute("""INSERT INTO chair_notes_fts(section_id,meeting,agenda,title,discussion,outcomes)
      SELECT s.id,m.name,a.number,coalesce(s.title,''),coalesce(s.discussion,''),
      coalesce(group_concat(o.outcome_type || ': ' || o.text,char(10)),'')
      FROM chair_note_sections s JOIN meetings m ON m.id=s.meeting_id
      LEFT JOIN agenda_items a ON a.id=s.agenda_item_id LEFT JOIN chair_note_outcomes o ON o.section_id=s.id GROUP BY s.id""")
    db.commit()
    return {"tdocs": tdocs, "fts_rows": db.execute("SELECT count(*) FROM tdocs_fts").fetchone()[0],
            "document_chunks": chunks,
            "chair_sections": chair_sections, "chair_outcomes": chair_outcomes}
