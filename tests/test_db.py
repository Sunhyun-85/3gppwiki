from ran2wiki.db import initialize


def test_schema_and_fts5(tmp_path) -> None:
    db = initialize(tmp_path / "ran2wiki.db")
    db.execute("INSERT INTO tdocs_fts(tdoc_id,title,body) VALUES (?,?,?)", ("R2-2500001", "Dynamic UE capability", "proposal details"))
    hit = db.execute("SELECT tdoc_id FROM tdocs_fts WHERE tdocs_fts MATCH ?", ('"dynamic UE capability"',)).fetchone()
    assert hit[0] == "R2-2500001"
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert {"meetings", "files", "tdocs", "chair_note_outcomes", "sync_runs"} <= tables

