from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from ran2wiki.classification import classify_text
from ran2wiki.config import ClassificationConfig, Config, PathsConfig
from ran2wiki.db import initialize
from ran2wiki.indexing import extract_pending, index_extracted
from ran2wiki.models import Classification, FileKind, RemoteEntry
from ran2wiki.sync.engine import sync_entries


def entry(size: int = 3, modified: int = 1) -> RemoteEntry:
    return RemoteEntry("R2-2501234.zip", "https://source/R2-2501234.zip", False,
                       datetime(2025, 1, modified, 12, 0), size, FileKind.TDOC)


def test_incremental_sync_is_idempotent_and_preserves_changed_version(tmp_path) -> None:
    db = initialize(tmp_path / "db.sqlite")
    first = sync_entries(db, tmp_path, "TSGR2_129", "https://source/129", [entry()], lambda _: b"one")
    second = sync_entries(db, tmp_path, "TSGR2_129", "https://source/129", [entry()], lambda _: (_ for _ in ()).throw(AssertionError("must not fetch")))
    third = sync_entries(db, tmp_path, "TSGR2_129", "https://source/129", [entry(3, 2)], lambda _: b"two")
    assert (first.downloaded, second.unchanged, third.changed) == (1, 1, 1)
    path = tmp_path / "raw/TSGR2_129/tdocs/R2-2501234.zip"
    assert path.read_bytes() == b"two"
    assert list(path.parent.glob("*.previous"))
    assert db.execute("SELECT count(*) FROM file_versions").fetchone()[0] == 2


def test_stable_modified_time_ignores_rounded_listing_size(tmp_path) -> None:
    db = initialize(tmp_path / "db.sqlite")
    sync_entries(db, tmp_path, "TSGR2_129", "https://source/129", [entry(size=4)], lambda _: b"one")
    same_listing_time = entry(size=3)
    result = sync_entries(
        db, tmp_path, "TSGR2_129", "https://source/129", [same_listing_time],
        lambda _: (_ for _ in ()).throw(AssertionError("must not refetch rounded size")),
    )
    assert result.unchanged == 1


def test_same_filename_from_docs_and_inbox_is_preserved_separately(tmp_path) -> None:
    db = initialize(tmp_path / "db.sqlite")
    entries = [
        RemoteEntry("R2-2501234.zip", "https://source/TSGR2_129/Docs/R2-2501234.zip", False,
                    datetime(2025, 1, 1), 4, FileKind.TDOC),
        RemoteEntry("R2-2501234.zip", "https://source/TSGR2_129/Inbox/R2-2501234.zip", False,
                    datetime(2025, 1, 1), 5, FileKind.TDOC),
    ]
    payloads = {entries[0].url: b"docs", entries[1].url: b"inbox"}
    sync_entries(db, tmp_path, "TSGR2_129", "https://source/TSGR2_129", entries,
                 payloads.__getitem__, workers=2)
    assert (tmp_path / "raw/TSGR2_129/tdocs/Docs/R2-2501234.zip").read_bytes() == b"docs"
    assert (tmp_path / "raw/TSGR2_129/tdocs/Inbox/R2-2501234.zip").read_bytes() == b"inbox"


def test_text_extraction_to_document_record(tmp_path) -> None:
    config = Config(paths=PathsConfig(tmp_path, tmp_path / "db.sqlite"))
    db = initialize(config.paths.database)
    source = tmp_path / "raw/TSGR2_129/metadata/notes.txt"
    source.parent.mkdir(parents=True)
    source.write_text("UE capability evidence")
    db.execute("INSERT INTO meetings(id,name,number,source_url) VALUES (1,'TSGR2_129',129,'https://source')")
    db.execute("INSERT INTO files(id,meeting_id,kind,filename,source_url,local_path) VALUES (1,1,'other','notes.txt','https://source/notes',?)", (str(source),))
    db.commit()
    assert extract_pending(db, config) == (1, 0)
    assert "UE capability" in db.execute("SELECT full_text FROM documents").fetchone()[0]
    structured = db.execute("SELECT structured_json_path FROM documents").fetchone()[0]
    assert Path(structured).name == "1-notes.txt.json"
    result = index_extracted(db, config)
    chunk = db.execute("SELECT ordinal,section,locator,text FROM document_chunks").fetchone()
    assert tuple(chunk) == (1, "text", "block:1", "UE capability evidence")
    assert result["document_chunks"] == 1


def test_tdoc_workbook_index_and_classification(tmp_path) -> None:
    config = Config(paths=PathsConfig(tmp_path, tmp_path / "db.sqlite"))
    db = initialize(config.paths.database)
    workbook_path = tmp_path / "list.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["TDoc No", "Title", "Source", "Agenda Item", "WI/SI", "Status"])
    ws.append(["R2-2501234", "6G mobility for IMT-2030", "Ericsson", "7.3", "6G_RAT", "discussion"])
    wb.save(workbook_path)
    db.execute("INSERT INTO meetings(id,name,number,source_url) VALUES (1,'TSGR2_131bis',131,'https://source')")
    db.execute("INSERT INTO files(id,meeting_id,kind,filename,source_url,local_path) VALUES (1,1,'tdoc_list','list.xlsx','https://source/list',?)", (str(workbook_path),))
    db.commit()
    result = index_extracted(db, config)
    row = db.execute("SELECT tdoc_id,source_company,classification FROM tdocs").fetchone()
    assert tuple(row) == ("R2-2501234", "Ericsson", "6G")
    assert result["fts_rows"] == 1
    assert db.execute("SELECT file_id FROM tdocs").fetchone()[0] == 1


def test_lightweight_classification_is_explicit() -> None:
    config = ClassificationConfig()
    assert classify_text("Rel-20 IMT-2030 6G study", None, config) == Classification.REL20_AND_6G
    assert classify_text("legacy administrative item", None, config) == Classification.OTHER
