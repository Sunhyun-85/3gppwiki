from ran2wiki.db import initialize
from ran2wiki.search import KnowledgeService


def seeded(tmp_path):
    db = initialize(tmp_path / "db.sqlite")
    db.execute("INSERT INTO meetings(id,name,number,suffix,source_url) VALUES (1,'TSGR2_131bis',131,'bis','https://source/meeting')")
    db.execute("INSERT INTO files(id,meeting_id,kind,filename,source_url) VALUES (1,1,'tdoc','R2-2501234.zip','https://source/tdoc')")
    db.execute("INSERT INTO files(id,meeting_id,kind,filename,source_url) VALUES (2,1,'chair_notes','chair.docx','https://source/chair')")
    db.execute("INSERT INTO agenda_items(id,meeting_id,number,title) VALUES (1,1,'7.3','UE capability')")
    db.execute("INSERT INTO tdocs(id,tdoc_id,meeting_id,title,source_company,agenda_item_id,status,file_id,classification) VALUES (1,'R2-2501234',1,'Dynamic UE capability','Samsung',1,'proposal',1,'REL20')")
    db.execute("INSERT INTO tdocs_fts(tdoc_id,title,body) VALUES ('R2-2501234','Dynamic UE capability','dynamic UE capability proposal')")
    db.execute("INSERT INTO chair_note_sections(id,meeting_id,file_id,agenda_item_id,ordinal,title,discussion,locator) VALUES (1,1,2,1,1,'UE capability','discussion','block:10')")
    db.execute("INSERT INTO chair_note_outcomes(section_id,outcome_type,text,locator) VALUES (1,'FFS','Dynamic UE capability reporting trigger remains open','block:11')")
    db.commit()
    return db


def test_search_has_provenance(tmp_path) -> None:
    service = KnowledgeService(seeded(tmp_path))
    hit = service.search_ran2("dynamic UE capability")[0]
    assert hit["tdoc_id"] == "R2-2501234"
    assert hit["source_url"] == "https://source/tdoc"
    assert hit["status"] == "proposal"


def test_find_agreements_and_trace_keep_type(tmp_path) -> None:
    service = KnowledgeService(seeded(tmp_path))
    outcome = service.find_agreements("dynamic")[0]
    assert outcome["outcome_type"] == "FFS"
    timeline = service.trace_topic("dynamic UE capability")
    assert timeline[0]["meeting"] == "TSGR2_131bis"
    assert timeline[0]["outcomes"][0]["outcome_type"] == "FFS"


def test_hierarchical_search_puts_chair_evidence_first(tmp_path) -> None:
    db = seeded(tmp_path)
    # Rebuild the Chair FTS row normally produced by the indexing pipeline.
    db.execute("INSERT INTO chair_notes_fts(section_id,meeting,agenda,title,discussion,outcomes) VALUES (1,'TSGR2_131bis','7.3','UE capability','dynamic capability discussion','FFS: Dynamic UE capability reporting trigger remains open')")
    db.commit()
    hits = KnowledgeService(db).search_ran2("dynamic", from_meeting="131", to_meeting="132", limit=5)
    assert hits[0]["evidence_type"] == "CHAIR_NOTES"
    assert hits[0]["outcome_type"] == "FFS"
    assert any(hit.get("tdoc_id") == "R2-2501234" for hit in hits)


def test_company_filter_applies_to_tdocs(tmp_path) -> None:
    service = KnowledgeService(seeded(tmp_path))
    assert service.search_ran2("dynamic", company="Samsung")
    assert service.search_ran2("dynamic", company="Ericsson") == []


def test_korean_natural_query_keeps_technical_search_terms(tmp_path) -> None:
    service = KnowledgeService(seeded(tmp_path))
    hits = service.search_ran2("동적 UE capability 관련 기고문을 찾아줘")
    assert any(hit.get("tdoc_id") == "R2-2501234" for hit in hits)
    outcomes = service.find_agreements("동적 UE capability 관련 FFS를 알려줘")
    assert outcomes[0]["outcome_type"] == "FFS"


def test_trace_chronology_does_not_use_two_from_tsgr2(tmp_path) -> None:
    db = seeded(tmp_path)
    db.execute("INSERT INTO meetings(id,name,number,suffix,source_url) VALUES (2,'TSGR2_132',132,'','https://132')")
    db.execute("INSERT INTO files(id,meeting_id,kind,filename,source_url) VALUES (3,2,'tdoc','R2-2600001.zip','https://132/doc')")
    db.execute("INSERT INTO tdocs(id,tdoc_id,meeting_id,title,file_id) VALUES (2,'R2-2600001',2,'Dynamic capability follow-up',3)")
    db.execute("INSERT INTO tdocs_fts(tdoc_id,title,body) VALUES ('R2-2600001','Dynamic capability follow-up','dynamic capability')")
    db.commit()
    timeline = KnowledgeService(db).trace_topic("dynamic")
    assert [item["meeting"] for item in timeline] == ["TSGR2_131bis", "TSGR2_132"]
