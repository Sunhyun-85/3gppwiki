from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS meetings (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, number INTEGER NOT NULL,
 group_name TEXT NOT NULL DEFAULT 'RAN2', suffix TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL, start_date TEXT,
 end_date TEXT, discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_checked TEXT, metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS files (
 id INTEGER PRIMARY KEY, meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, filename TEXT NOT NULL, source_url TEXT NOT NULL UNIQUE,
 size INTEGER, remote_modified TEXT, sha256 TEXT, first_downloaded TEXT,
 last_checked TEXT, local_path TEXT, extraction_status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_files_meeting_kind ON files(meeting_id, kind);
CREATE TABLE IF NOT EXISTS file_versions (
 id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
 sha256 TEXT NOT NULL, size INTEGER NOT NULL, remote_modified TEXT, local_path TEXT NOT NULL,
 downloaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(file_id, sha256)
);
CREATE TABLE IF NOT EXISTS agenda_items (
 id INTEGER PRIMARY KEY, meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
 number TEXT NOT NULL, title TEXT, parent_id INTEGER REFERENCES agenda_items(id),
 UNIQUE(meeting_id, number)
);
CREATE TABLE IF NOT EXISTS tdocs (
 id INTEGER PRIMARY KEY, tdoc_id TEXT NOT NULL UNIQUE, meeting_id INTEGER REFERENCES meetings(id),
 title TEXT, source_company TEXT, agenda_item_id INTEGER REFERENCES agenda_items(id),
 work_item TEXT, status TEXT, revision_of TEXT, comments TEXT, file_id INTEGER REFERENCES files(id),
 classification TEXT NOT NULL DEFAULT 'UNKNOWN'
);
CREATE INDEX IF NOT EXISTS idx_tdocs_meeting ON tdocs(meeting_id);
CREATE INDEX IF NOT EXISTS idx_tdocs_company ON tdocs(source_company);
CREATE TABLE IF NOT EXISTS documents (
 id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL UNIQUE REFERENCES files(id) ON DELETE CASCADE,
 tdoc_id INTEGER REFERENCES tdocs(id), title TEXT, full_text TEXT NOT NULL DEFAULT '',
 structured_json_path TEXT, extractor_version TEXT
);
CREATE TABLE IF NOT EXISTS document_chunks (
 id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, section TEXT, locator TEXT, text TEXT NOT NULL,
 UNIQUE(document_id, ordinal)
);
CREATE TABLE IF NOT EXISTS chair_note_sections (
 id INTEGER PRIMARY KEY, meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
 file_id INTEGER NOT NULL REFERENCES files(id), agenda_item_id INTEGER REFERENCES agenda_items(id),
 ordinal INTEGER NOT NULL, title TEXT, discussion TEXT, locator TEXT,
 UNIQUE(file_id, ordinal)
);
CREATE TABLE IF NOT EXISTS chair_note_outcomes (
 id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL REFERENCES chair_note_sections(id) ON DELETE CASCADE,
 outcome_type TEXT NOT NULL CHECK(outcome_type IN ('AGREEMENT','CONCLUSION','FFS','POSTPONED','NOTED')),
 text TEXT NOT NULL, locator TEXT
);
CREATE INDEX IF NOT EXISTS idx_outcomes_type ON chair_note_outcomes(outcome_type);
CREATE TABLE IF NOT EXISTS chair_section_tdocs (
 section_id INTEGER NOT NULL REFERENCES chair_note_sections(id) ON DELETE CASCADE,
 tdoc_id INTEGER NOT NULL REFERENCES tdocs(id) ON DELETE CASCADE,
 PRIMARY KEY(section_id, tdoc_id)
);
CREATE TABLE IF NOT EXISTS tdoc_relationships (
 id INTEGER PRIMARY KEY, from_tdoc_id INTEGER REFERENCES tdocs(id), to_tdoc_id INTEGER REFERENCES tdocs(id),
 section_id INTEGER REFERENCES chair_note_sections(id), relationship_type TEXT NOT NULL,
 evidence_text TEXT, UNIQUE(from_tdoc_id, to_tdoc_id, section_id, relationship_type)
);
CREATE TABLE IF NOT EXISTS topics (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, aliases_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS sync_runs (
 id INTEGER PRIMARY KEY, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT,
 group_name TEXT NOT NULL DEFAULT 'RAN2', status TEXT NOT NULL, discovered_count INTEGER NOT NULL DEFAULT 0,
 downloaded_count INTEGER NOT NULL DEFAULT 0, changed_count INTEGER NOT NULL DEFAULT 0,
 error TEXT
);
CREATE TABLE IF NOT EXISTS app_state (
 key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS tdocs_fts USING fts5(tdoc_id UNINDEXED, title, body, tokenize='unicode61');
CREATE VIRTUAL TABLE IF NOT EXISTS chair_notes_fts USING fts5(section_id UNINDEXED, meeting UNINDEXED, agenda, title, discussion, outcomes, tokenize='unicode61');
CREATE VIRTUAL TABLE IF NOT EXISTS agenda_fts USING fts5(agenda_id UNINDEXED, meeting UNINDEXED, number, title, tokenize='unicode61');
"""


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def migrate(connection: sqlite3.Connection) -> None:
    """Apply compatibility-safe additive migrations; existing RAN2 rows keep their meaning."""
    if "group_name" not in _columns(connection, "meetings"):
        connection.execute("ALTER TABLE meetings ADD COLUMN group_name TEXT NOT NULL DEFAULT 'RAN2'")
    if "group_name" not in _columns(connection, "sync_runs"):
        connection.execute("ALTER TABLE sync_runs ADD COLUMN group_name TEXT NOT NULL DEFAULT 'RAN2'")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_meetings_group_number ON meetings(group_name,number,suffix)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_sync_runs_group ON sync_runs(group_name,id)")
    connection.execute("PRAGMA user_version = 2")


def connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(db_path)
    connection.executescript(SCHEMA)
    migrate(connection)
    connection.commit()
    return connection
