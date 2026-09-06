from __future__ import annotations

import re
import sqlite3
from typing import Any

from ran2wiki.models import meeting_sort_key
from ran2wiki.groups import get_group_adapter


QUERY_ALIASES = {
    "동적 ue capability": "dynamic UE capability",
    "단말 능력": "UE capability",
    "단말 capability": "UE capability",
    "이동성": "mobility",
    "모빌리티": "mobility",
    "핸드오버": "handover",
    "측정": "measurement",
    "무선 자원 제어": "RRC",
}
STOPWORDS = {
    "about", "and", "documents", "find", "from", "in", "of", "on", "ran2",
    "related", "show", "the", "to", "was", "were", "what",
}


def _query_tokens(query: str) -> list[str]:
    expanded = query.casefold()
    aliases: list[str] = []
    for phrase, replacement in QUERY_ALIASES.items():
        if phrase in expanded:
            expanded = expanded.replace(phrase, " ")
            aliases.extend(re.findall(r"[\w-]+", replacement, re.UNICODE))
    tokens = aliases + re.findall(r"[\w-]+", expanded, re.UNICODE)
    return list(dict.fromkeys(
        token for token in tokens
        if token.casefold() not in STOPWORDS and not re.search(r"[가-힣]", token)
    ))[:20]


def _fts_query(query: str, operator: str = "AND") -> str:
    tokens = _query_tokens(query)
    if not tokens:
        raise ValueError("query must contain a searchable technical term")
    return f" {operator} ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens[:20])


def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


class KnowledgeService:
    """Compact provenance-bearing access to the local knowledge database."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def status(self, group: str = "RAN2") -> dict[str, Any]:
        """Return inexpensive database statistics for local user interfaces."""
        latest = self.db.execute(
            "SELECT name FROM meetings WHERE group_name=? ORDER BY number DESC, suffix DESC LIMIT 1", (group,)
        ).fetchone()
        last_sync = self.db.execute(
            "SELECT finished_at FROM sync_runs WHERE group_name=? AND status='success' ORDER BY id DESC LIMIT 1", (group,)
        ).fetchone()
        current_sync = self.db.execute("""
          SELECT id,started_at,finished_at,status,discovered_count,downloaded_count,
                 changed_count,error FROM sync_runs WHERE group_name=? ORDER BY id DESC LIMIT 1
        """, (group,)).fetchone()
        return {
            "meetings": self.db.execute("SELECT count(*) FROM meetings WHERE group_name=?", (group,)).fetchone()[0],
            "tdocs": self.db.execute("SELECT count(*) FROM tdocs t JOIN meetings m ON m.id=t.meeting_id WHERE m.group_name=?", (group,)).fetchone()[0],
            "rel20_tdocs": self.db.execute(
                "SELECT count(*) FROM tdocs t JOIN meetings m ON m.id=t.meeting_id WHERE m.group_name=? AND classification IN ('REL20','REL20_AND_6G')", (group,)
            ).fetchone()[0],
            "six_g_tdocs": self.db.execute(
                "SELECT count(*) FROM tdocs t JOIN meetings m ON m.id=t.meeting_id WHERE m.group_name=? AND classification IN ('6G','REL20_AND_6G')", (group,)
            ).fetchone()[0],
            "chair_sections": self.db.execute("SELECT count(*) FROM chair_note_sections s JOIN meetings m ON m.id=s.meeting_id WHERE m.group_name=?", (group,)).fetchone()[0],
            "latest_meeting": latest[0] if latest else None,
            "last_sync": last_sync[0] if last_sync else None,
            "sync_run": dict(current_sync) if current_sync else None,
        }

    def list_meetings(self, limit: int = 100, group: str = "RAN2") -> list[dict[str, Any]]:
        return _rows(self.db.execute("""
          SELECT m.group_name AS `group`,m.name,m.number,m.suffix,m.start_date,m.end_date,m.source_url,m.last_checked,
                 count(DISTINCT t.id) AS tdoc_count,
                 count(DISTINCT s.id) AS chair_section_count
          FROM meetings m LEFT JOIN tdocs t ON t.meeting_id=m.id
          LEFT JOIN chair_note_sections s ON s.meeting_id=m.id
          WHERE m.group_name=? GROUP BY m.id ORDER BY m.number DESC,m.suffix DESC LIMIT ?
        """, (group, max(1, min(limit, 500)))).fetchall())

    def audit(self, group: str = "RAN2", sample_limit: int = 20) -> dict[str, Any]:
        """Return deterministic corpus quality metrics without loading document bodies."""
        extraction = _rows(self.db.execute("""
          SELECT f.extraction_status,count(*) AS count FROM files f
          JOIN meetings m ON m.id=f.meeting_id WHERE m.group_name=?
          GROUP BY f.extraction_status ORDER BY f.extraction_status
        """, (group,)).fetchall())
        tdocs = self.db.execute("""SELECT count(*) FROM tdocs t JOIN meetings m
          ON m.id=t.meeting_id WHERE m.group_name=?""", (group,)).fetchone()[0]
        linked = self.db.execute("""SELECT count(DISTINCT t.id) FROM tdocs t
          JOIN meetings m ON m.id=t.meeting_id JOIN documents d ON d.tdoc_id=t.id
          WHERE m.group_name=?""", (group,)).fetchone()[0]
        return {
            "group": group,
            "integrity": self.db.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_errors": len(self.db.execute("PRAGMA foreign_key_check").fetchall()),
            "extraction_status": extraction,
            "tdocs_total": tdocs,
            "tdocs_with_extracted_content": linked,
            "tdoc_content_coverage": round(linked / tdocs, 6) if tdocs else 0.0,
            "chair_sections": self.db.execute("""SELECT count(*) FROM chair_note_sections s
              JOIN meetings m ON m.id=s.meeting_id WHERE m.group_name=?""", (group,)).fetchone()[0],
            "outcomes_by_type": _rows(self.db.execute("""SELECT o.outcome_type,count(*) AS count
              FROM chair_note_outcomes o JOIN chair_note_sections s ON s.id=o.section_id
              JOIN meetings m ON m.id=s.meeting_id WHERE m.group_name=?
              GROUP BY o.outcome_type ORDER BY o.outcome_type""", (group,)).fetchall()),
            "meetings_without_indexed_chair_notes": [row[0] for row in self.db.execute("""
              SELECT m.name FROM meetings m WHERE m.group_name=? AND NOT EXISTS
              (SELECT 1 FROM chair_note_sections s WHERE s.meeting_id=m.id)
              ORDER BY m.number,m.suffix""", (group,)).fetchall()],
            "failed_extraction_samples": _rows(self.db.execute("""
              SELECT m.name AS meeting,f.filename,f.kind,f.local_path,f.source_url
              FROM files f JOIN meetings m ON m.id=f.meeting_id
              WHERE m.group_name=? AND f.extraction_status='failed'
              ORDER BY m.number,m.suffix,f.filename LIMIT ?
            """, (group, max(1, min(sample_limit, 100)))).fetchall()),
            "tdoc_fts_rows": self.db.execute("SELECT count(*) FROM tdocs_fts").fetchone()[0],
            "chair_fts_rows": self.db.execute("SELECT count(*) FROM chair_notes_fts").fetchone()[0],
            "document_chunks": self.db.execute("""SELECT count(*) FROM document_chunks c
              JOIN documents d ON d.id=c.document_id JOIN files f ON f.id=d.file_id
              JOIN meetings m ON m.id=f.meeting_id WHERE m.group_name=?""", (group,)).fetchone()[0],
        }

    def _search_tdocs(self, query: str, scope: str, meeting: str | None, from_meeting: str | None,
                      to_meeting: str | None, agenda: str | None, company: str | None,
                      limit: int, group: str, release: str | None) -> list[dict[str, Any]]:
        match = _fts_query(query)
        sql = """
          SELECT 'TDOC' AS evidence_type,m.group_name AS `group`,t.tdoc_id, t.title, t.source_company AS company, t.status,
                 t.classification AS scope, m.name AS meeting,m.start_date AS meeting_date, a.number AS agenda,
                 f.filename AS source_file, f.source_url,f.local_path AS local_source_path,
                 CASE WHEN d.full_text!='' THEN snippet(tdocs_fts, 2, '[', ']', ' … ', 40)
                      ELSE t.title END AS relevant_text,
                 bm25(tdocs_fts, 5.0, 3.0, 1.0) AS rank
          FROM tdocs_fts JOIN tdocs t ON t.tdoc_id=tdocs_fts.tdoc_id
          LEFT JOIN meetings m ON m.id=t.meeting_id
          LEFT JOIN agenda_items a ON a.id=t.agenda_item_id
          LEFT JOIN files f ON f.id=t.file_id
          LEFT JOIN documents d ON d.tdoc_id=t.id
          WHERE tdocs_fts MATCH ? AND m.group_name=?
        """
        params: list[Any] = [match, group]
        if scope != "ALL":
            sql += " AND t.classification IN (?, 'REL20_AND_6G')"
            params.append(scope)
        if release:
            if release.strip().casefold() not in {"20", "rel20", "rel-20", "release 20"}:
                return []
            sql += " AND t.classification IN ('REL20','REL20_AND_6G')"
        canonical = get_group_adapter(group).meeting_name(meeting) if meeting else None
        for clause, value in (("m.name IN (?,?)", (meeting, canonical) if meeting else None),
                              ("m.number>=?", int(''.join(c for c in from_meeting or '' if c.isdigit())) if from_meeting else None),
                              ("m.number<=?", int(''.join(c for c in to_meeting or '' if c.isdigit())) if to_meeting else None),
                              ("a.number=?", agenda), ("t.source_company LIKE ?", f"%{company}%" if company else None)):
            if value:
                sql += f" AND {clause}"
                params.extend(value if isinstance(value, tuple) else (value,))
        sql += " ORDER BY rank LIMIT ?"
        params.append(max(1, min(limit, 50)))
        return _rows(self.db.execute(sql, params).fetchall())

    def _search_chair(self, query: str, meeting: str | None, from_meeting: str | None,
                      to_meeting: str | None, agenda: str | None, limit: int, group: str) -> list[dict[str, Any]]:
        sql = """
          SELECT 'CHAIR_NOTES' AS evidence_type,m.group_name AS `group`,NULL AS tdoc_id,s.title,NULL AS company,NULL AS status,
                 'ALL' AS scope,m.name AS meeting,m.start_date AS meeting_date,a.number AS agenda,f.filename AS source_file,f.source_url,f.local_path AS local_source_path,
                 snippet(chair_notes_fts,-1,'[',']',' … ',50) AS relevant_text,
                 bm25(chair_notes_fts,0,0,2,3,5,8) AS rank,s.locator,s.id AS section_id
          FROM chair_notes_fts JOIN chair_note_sections s ON s.id=chair_notes_fts.section_id
          JOIN meetings m ON m.name=chair_notes_fts.meeting LEFT JOIN agenda_items a ON a.id=s.agenda_item_id
          JOIN files f ON f.id=s.file_id
          WHERE chair_notes_fts MATCH ? AND m.group_name=?
        """
        params: list[Any] = [_fts_query(query), group]
        canonical = get_group_adapter(group).meeting_name(meeting) if meeting else None
        for clause, value in (("m.name IN (?,?)", (meeting, canonical) if meeting else None),
                              ("m.number>=?", int(''.join(c for c in from_meeting or '' if c.isdigit())) if from_meeting else None),
                              ("m.number<=?", int(''.join(c for c in to_meeting or '' if c.isdigit())) if to_meeting else None),
                              ("a.number=?", agenda)):
            if value:
                sql += f" AND {clause}"
                params.extend(value if isinstance(value, tuple) else (value,))
        sql += " ORDER BY rank LIMIT ?"
        params.append(max(1, min(limit, 50)))
        results = _rows(self.db.execute(sql, params).fetchall())
        for result in results:
            if result.get("tdoc_id"):
                actual = self.db.execute("""
                  SELECT filename,source_url,local_path FROM files f JOIN meetings m ON m.id=f.meeting_id
                  WHERE m.name=? AND m.group_name=? AND f.kind='tdoc'
                  AND replace(f.filename,'_','-') LIKE ? ORDER BY
                  CASE WHEN f.source_url LIKE '%/Docs/%' THEN 0 ELSE 1 END,f.id LIMIT 1
                """, (result.get("meeting"), group, f"{result['tdoc_id']}%")).fetchone()
                if actual:
                    result["metadata_source_file"] = result.get("source_file")
                    result["metadata_source_url"] = result.get("source_url")
                    result["source_file"] = actual["filename"]
                    result["source_url"] = actual["source_url"]
                    result["local_source_path"] = actual["local_path"]
            outcomes = self.db.execute("SELECT outcome_type,text FROM chair_note_outcomes WHERE section_id=? ORDER BY id",
                                       (result.pop("section_id"),)).fetchall()
            result["outcome_type"] = ",".join(dict.fromkeys(row["outcome_type"] for row in outcomes)) or None
            matching = [f"{row['outcome_type']}: {row['text']}" for row in outcomes
                        if any(token.casefold() in row["text"].casefold() for token in _query_tokens(query))]
            if matching:
                result["relevant_text"] = "\n".join(matching[:8])
        return results

    def search_ran2(self, query: str, scope: str = "ALL", meeting: str | None = None,
                    from_meeting: str | None = None, to_meeting: str | None = None,
                    agenda: str | None = None, company: str | None = None,
                    limit: int = 10, group: str = "RAN2", release: str | None = None) -> list[dict[str, Any]]:
        """Hierarchical search: meeting conclusions first, then detailed TDocs."""
        chair_limit = max(1, limit // 3)
        try:
            chair = self._search_chair(query, meeting, from_meeting, to_meeting, agenda, chair_limit, group)
        except sqlite3.OperationalError:
            chair = []
        tdocs = self._search_tdocs(query, scope, meeting, from_meeting, to_meeting, agenda, company, limit, group, release)
        results = (chair + tdocs)[:max(1, min(limit, 50))]
        for result in results:
            result["source"] = result.get("company")
            result["document_status"] = result.get("status")
            result["section"] = result.get("locator")
            result["snippet"] = result.get("relevant_text")
            result["relevance"] = result.get("rank")
            if result.get("evidence_type") == "CHAIR_NOTES":
                result["event_type"] = result.get("outcome_type") or "DISCUSSION"
            elif "proposal" in (result.get("status") or "").casefold():
                result["event_type"] = "PROPOSAL"
            else:
                result["event_type"] = "DOCUMENT"
        return results

    def get_tdoc(self, tdoc_id: str, group: str = "RAN2") -> dict[str, Any] | None:
        tdoc_id = get_group_adapter(group).normalize_tdoc_id(tdoc_id)
        row = self.db.execute("""
          SELECT m.group_name AS `group`,t.tdoc_id,t.title,t.source_company AS company,t.status,t.work_item,t.classification,
                 m.name AS meeting,m.start_date AS meeting_date,a.number AS agenda,d.full_text,f.filename AS source_file,f.source_url,f.local_path AS local_source_path
          FROM tdocs t LEFT JOIN meetings m ON m.id=t.meeting_id LEFT JOIN agenda_items a ON a.id=t.agenda_item_id
          LEFT JOIN documents d ON d.tdoc_id=t.id LEFT JOIN files f ON f.id=t.file_id WHERE t.tdoc_id=? AND m.group_name=?
        """, (tdoc_id, group)).fetchone()
        if row is None:
            return None
        result = dict(row)
        actual = self.db.execute("""
          SELECT f.filename,f.source_url,f.local_path FROM files f JOIN meetings m ON m.id=f.meeting_id
          WHERE m.name=? AND m.group_name=? AND f.kind='tdoc' AND replace(f.filename,'_','-') LIKE ?
          ORDER BY CASE WHEN f.source_url LIKE '%/Docs/%' THEN 0 ELSE 1 END,f.id LIMIT 1
        """, (result["meeting"], group, f"{tdoc_id}%")).fetchone()
        if actual:
            result["metadata_source_file"] = result.get("source_file")
            result["metadata_source_url"] = result.get("source_url")
            result["source_file"] = actual["filename"]
            result["source_url"] = actual["source_url"]
            result["local_source_path"] = actual["local_path"]
        result["chair_notes_references"] = _rows(self.db.execute("""
          SELECT m.name AS meeting,a.number AS agenda,s.title,s.locator,f.filename AS source_file,f.source_url
          FROM chair_section_tdocs r JOIN chair_note_sections s ON s.id=r.section_id
          JOIN meetings m ON m.id=s.meeting_id LEFT JOIN agenda_items a ON a.id=s.agenda_item_id
          JOIN files f ON f.id=s.file_id JOIN tdocs t ON t.id=r.tdoc_id
            WHERE t.tdoc_id=? AND m.group_name=?
        """, (tdoc_id, group)).fetchall())
        return result

    def get_meeting(self, meeting: str, group: str = "RAN2") -> dict[str, Any] | None:
        canonical = get_group_adapter(group).meeting_name(meeting)
        row = self.db.execute("SELECT * FROM meetings WHERE (name=? OR name=?) AND group_name=?", (meeting, canonical, group)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["agenda"] = _rows(self.db.execute("SELECT number,title FROM agenda_items WHERE meeting_id=? ORDER BY id", (row["id"],)).fetchall())
        result["tdoc_count"] = self.db.execute("SELECT count(*) FROM tdocs WHERE meeting_id=?", (row["id"],)).fetchone()[0]
        result["chair_notes_available"] = bool(self.db.execute("SELECT 1 FROM chair_note_sections WHERE meeting_id=? LIMIT 1", (row["id"],)).fetchone())
        result["outcome_summary"] = _rows(self.db.execute("""SELECT o.outcome_type,count(*) AS count FROM chair_note_outcomes o JOIN chair_note_sections s ON s.id=o.section_id WHERE s.meeting_id=? GROUP BY o.outcome_type ORDER BY o.outcome_type""", (row["id"],)).fetchall())
        result["local_source_locations"] = [r[0] for r in self.db.execute("SELECT DISTINCT local_path FROM files WHERE meeting_id=? AND local_path IS NOT NULL ORDER BY local_path", (row["id"],)).fetchall()]
        return result

    def get_chair_notes(self, meeting: str, agenda: str | None = None, group: str = "RAN2",
                        limit: int = 100) -> list[dict[str, Any]]:
        canonical = get_group_adapter(group).meeting_name(meeting)
        sql = """
          SELECT m.group_name AS `group`,m.name AS meeting,a.number AS agenda,s.title,s.discussion,s.locator,
                 f.filename AS source_file,f.source_url,f.local_path AS local_source_path,
                 coalesce(group_concat(o.outcome_type || ': ' || o.text, char(10)), '') AS outcomes
          FROM chair_note_sections s JOIN meetings m ON m.id=s.meeting_id
          LEFT JOIN agenda_items a ON a.id=s.agenda_item_id JOIN files f ON f.id=s.file_id
          LEFT JOIN chair_note_outcomes o ON o.section_id=s.id WHERE (m.name=? OR m.name=?) AND m.group_name=?
        """
        params: list[Any] = [meeting, canonical, group]
        if agenda:
            sql += " AND a.number=?"
            params.append(agenda)
        sql += " GROUP BY s.id ORDER BY s.ordinal LIMIT ?"
        params.append(max(1, min(limit, 500)))
        return _rows(self.db.execute(sql, params).fetchall())

    def find_agreements(self, query: str, outcome_type: str = "ALL", limit: int = 20, group: str = "RAN2") -> list[dict[str, Any]]:
        query_tokens = _query_tokens(query)
        mentioned_types = tuple(
            token.upper() for token in query_tokens
            if token.upper() in {"AGREEMENT", "CONCLUSION", "FFS"}
        )
        types = mentioned_types or (("AGREEMENT", "CONCLUSION", "FFS") if outcome_type == "ALL" else (outcome_type,))
        placeholders = ",".join("?" for _ in types)
        terms = [f"%{token}%" for token in query_tokens
                 if token.upper() not in {"AGREEMENT", "CONCLUSION", "FFS"}][:10] or ["%"]
        sql = f"""
          SELECT m.group_name AS `group`,o.outcome_type,o.text,m.name AS meeting,m.start_date AS meeting_date,a.number AS agenda,s.title,s.locator,
                 f.filename AS source_file,f.source_url,f.local_path AS local_source_path
          FROM chair_note_outcomes o JOIN chair_note_sections s ON s.id=o.section_id
          JOIN meetings m ON m.id=s.meeting_id LEFT JOIN agenda_items a ON a.id=s.agenda_item_id
          JOIN files f ON f.id=s.file_id WHERE o.outcome_type IN ({placeholders}) AND m.group_name=?
          AND ({' AND '.join('o.text LIKE ?' for _ in terms)}) ORDER BY m.number,m.suffix,s.ordinal LIMIT ?
        """
        return _rows(self.db.execute(sql, [*types, group, *terms, max(1, min(limit, 50))]).fetchall())

    def trace_topic(self, query: str, limit_per_meeting: int = 8, group: str = "RAN2", scope: str = "ALL") -> list[dict[str, Any]]:
        hits = self.search_ran2(query, scope=scope, limit=50, group=group)
        timeline: dict[str, dict[str, Any]] = {}
        for hit in hits:
            meeting = hit.get("meeting") or "UNKNOWN"
            bucket = timeline.setdefault(meeting, {"meeting": meeting, "chair_evidence": [], "tdocs": [], "outcomes": []})
            bucket["chair_evidence" if hit.get("evidence_type") == "CHAIR_NOTES" else "tdocs"].append(hit)
        for outcome in self.find_agreements(query, limit=50, group=group):
            meeting = outcome["meeting"]
            timeline.setdefault(meeting, {"meeting": meeting, "chair_evidence": [], "tdocs": [], "outcomes": []})["outcomes"].append(outcome)
        def key(item: dict[str, Any]) -> tuple[int, int]:
            number, suffix_rank, _ = meeting_sort_key(item["meeting"])
            return number, suffix_rank
        for item in timeline.values():
            item["tdocs"] = item["tdocs"][:limit_per_meeting]
            item["chair_evidence"] = item["chair_evidence"][:limit_per_meeting]
            item["outcomes"] = item["outcomes"][:limit_per_meeting]
        return sorted(timeline.values(), key=key)
