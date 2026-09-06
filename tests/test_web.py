from importlib.resources import files

from ran2wiki.db import initialize
from ran2wiki.search import KnowledgeService


def test_web_asset_is_packaged() -> None:
    page = files("ran2wiki.web").joinpath("index.html").read_text(encoding="utf-8")
    assert "RAN2 Wiki" in page
    assert "LLM/API 없이 동작" in page
    assert 'data-view="chair-notes"' in page


def test_status_and_meeting_list(tmp_path) -> None:
    db = initialize(tmp_path / "ran2wiki.db")
    db.execute(
        "INSERT INTO meetings(name,number,suffix,source_url) VALUES ('TSGR2_131bis',131,'bis','https://source')"
    )
    db.commit()
    service = KnowledgeService(db)
    assert service.status()["meetings"] == 1
    assert service.status()["tdocs"] == 0
    assert service.status()["sync_run"] is None
    assert service.list_meetings()[0]["name"] == "TSGR2_131bis"
