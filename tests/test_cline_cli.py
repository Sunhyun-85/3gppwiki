import json
import sqlite3
from argparse import Namespace

from ran2wiki.cli import main
from ran2wiki import cli
from ran2wiki.db import initialize
from ran2wiki.groups import get_group_adapter
from ran2wiki.search import KnowledgeService


def config_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        f"paths:\n  data_dir: {tmp_path / 'data'}\n  database: {tmp_path / 'wiki.db'}\n",
        encoding="utf-8",
    )
    return path


def seed(path):
    db = initialize(path)
    db.execute("INSERT INTO meetings(id,name,number,suffix,source_url,group_name) VALUES (1,'TSGR2_131bis',131,'bis','https://meeting','RAN2')")
    db.execute("INSERT INTO files(id,meeting_id,kind,filename,source_url,local_path) VALUES (1,1,'tdoc','R2-2501234.zip','https://tdoc','data/raw/TSGR2_131bis/tdocs/R2-2501234.zip')")
    db.execute("INSERT INTO files(id,meeting_id,kind,filename,source_url,local_path) VALUES (2,1,'chair_notes','chair.docx','https://chair','data/raw/TSGR2_131bis/chair_notes/chair.docx')")
    db.execute("INSERT INTO agenda_items(id,meeting_id,number,title) VALUES (1,1,'7.3','UE capability')")
    db.execute("INSERT INTO tdocs(id,tdoc_id,meeting_id,title,source_company,agenda_item_id,status,file_id,classification) VALUES (1,'R2-2501234',1,'Dynamic UE capability','Samsung',1,'proposal',1,'REL20')")
    db.execute("INSERT INTO documents(file_id,tdoc_id,full_text) VALUES (1,1,'long proposal body')")
    db.execute("INSERT INTO tdocs_fts(tdoc_id,title,body) VALUES ('R2-2501234','Dynamic UE capability','dynamic UE capability proposal')")
    db.execute("INSERT INTO chair_note_sections(id,meeting_id,file_id,agenda_item_id,ordinal,title,discussion,locator) VALUES (1,1,2,1,1,'UE capability','discussion','paragraph:10')")
    db.execute("INSERT INTO chair_note_outcomes(section_id,outcome_type,text,locator) VALUES (1,'FFS','Dynamic UE capability remains open','paragraph:11')")
    db.execute("INSERT INTO chair_notes_fts(section_id,meeting,agenda,title,discussion,outcomes) VALUES (1,'TSGR2_131bis','7.3','UE capability','dynamic capability discussion','FFS: Dynamic UE capability remains open')")
    db.commit()
    db.close()


def test_json_search_and_compact_tdoc(tmp_path, capsys):
    config = config_file(tmp_path)
    seed(tmp_path / "wiki.db")
    assert main(["--config", str(config), "search", "dynamic UE capability", "--group", "RAN2", "--release", "20", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    hit = next(row for row in payload["results"] if row["tdoc_id"])
    assert hit["group"] == "RAN2"
    assert hit["document_status"] == "proposal"
    assert hit["local_source_path"].endswith("R2-2501234.zip")

    assert main(["--config", str(config), "tdoc", "R2_2501234", "--json", "--max-chars", "4"]) == 0
    tdoc = json.loads(capsys.readouterr().out)["result"]
    assert tdoc["content_excerpt"] == "long"
    assert tdoc["content_truncated"] is True


def test_group_filter_trace_outcomes_and_status(tmp_path, capsys):
    config = config_file(tmp_path)
    seed(tmp_path / "wiki.db")
    db = initialize(tmp_path / "wiki.db")
    assert KnowledgeService(db).search_ran2("dynamic", group="RAN3") == []
    db.close()
    for command in (
        ["trace", "dynamic", "--group", "RAN2", "--json"],
        ["outcomes", "dynamic", "--group", "RAN2", "--types", "FFS", "--json"],
        ["status", "--json"],
    ):
        assert main(["--config", str(config), *command]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema_version"] == 1
    assert payload["groups"]["RAN2"]["enabled"] is True
    assert payload["groups"]["RAN3"]["enabled"] is False


def test_audit_json_reports_quality_and_provenance_coverage(tmp_path, capsys):
    config = config_file(tmp_path)
    seed(tmp_path / "wiki.db")
    assert main(["--config", str(config), "audit", "--group", "RAN2", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    audit = payload["result"]
    assert audit["integrity"] == "ok"
    assert audit["foreign_key_errors"] == 0
    assert audit["tdocs_with_extracted_content"] == 1
    assert audit["tdoc_content_coverage"] == 1.0
    assert audit["outcomes_by_type"] == [{"outcome_type": "FFS", "count": 1}]


def test_additive_migration_and_native_tdoc_prefixes(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE meetings(id INTEGER PRIMARY KEY,name TEXT UNIQUE,number INTEGER NOT NULL,suffix TEXT NOT NULL DEFAULT '',source_url TEXT NOT NULL,start_date TEXT,end_date TEXT,discovered_at TEXT,last_checked TEXT,metadata_json TEXT)")
    db.execute("CREATE TABLE sync_runs(id INTEGER PRIMARY KEY,started_at TEXT,finished_at TEXT,status TEXT,discovered_count INTEGER,downloaded_count INTEGER,changed_count INTEGER,error TEXT)")
    db.execute("INSERT INTO meetings(name,number,source_url) VALUES ('TSGR2_125',125,'local')")
    db.commit(); db.close()
    migrated = initialize(path)
    assert migrated.execute("SELECT group_name FROM meetings").fetchone()[0] == "RAN2"
    assert migrated.execute("PRAGMA user_version").fetchone()[0] == 2
    migrated.close()
    assert get_group_adapter("RAN3").normalize_tdoc_id("R3_2601234") == "R3-2601234"
    assert get_group_adapter("RAN4").meeting_name("120") == "TSGR4_120"


def test_update_json_report_is_machine_readable(tmp_path, capsys, monkeypatch):
    config = config_file(tmp_path)
    initialize(tmp_path / "wiki.db").close()

    def fake_update(args):
        db = initialize(tmp_path / "wiki.db")
        db.execute("INSERT INTO sync_runs(group_name,status,discovered_count,downloaded_count,changed_count) VALUES ('RAN2','success',4,2,1)")
        db.commit(); db.close()
        print("human progress")
        return 0

    monkeypatch.setattr(cli, "_run_update", fake_update)
    args = Namespace(config=str(config), group="RAN2", json=True, value=None, meeting=None)
    assert cli._cmd_update_json(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert payload["files_checked"] == 4
    assert payload["files_downloaded"] == 2
    assert payload["files_changed"] == 1
