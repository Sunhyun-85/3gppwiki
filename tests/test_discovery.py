from pathlib import Path

from ran2wiki.models import FileKind
from ran2wiki.sync.discovery import discover_meetings, encoded_url, filter_meetings, parse_listing, parse_size
from ran2wiki.sync.engine import select_meetings_for_update

FIXTURES = Path(__file__).parent / "fixtures"


def test_meeting_discovery_respects_boundary_and_bis_order() -> None:
    html = (FIXTURES / "listing.html").read_text()
    found = discover_meetings(html, "https://example.test/root/", "125", "126")
    assert [entry.name for entry in found] == ["TSGR2_125", "TSGR2_125bis", "TSGR2_126"]


def test_file_discovery_classifies_primary_sources() -> None:
    html = (FIXTURES / "meeting_listing.html").read_text()
    found = parse_listing(html, "https://example.test/TSGR2_131bis/")
    kinds = {entry.name: entry.kind for entry in found}
    assert kinds["R2_131bis_ChairNotes.docx"] == FileKind.CHAIR_NOTES
    assert kinds["TDoc_List_Meeting_RAN2#131bis.xlsx"] == FileKind.TDOC_LIST
    assert kinds["R2-2506704.zip"] == FileKind.TDOC
    assert kinds["R2-2508002.zip"] == FileKind.TDOC
    chair = next(entry for entry in found if entry.name == "R2_131bis_ChairNotes.docx")
    assert chair.modified_at.isoformat() == "2025-10-12T16:44:00"
    assert chair.size == round(237.8 * 1024)


def test_size_and_hash_url_handling() -> None:
    assert parse_size("237,8 KB") == round(237.8 * 1024)
    url = encoded_url("https://example.test/Docs/", "TDoc_List_RAN2#129.xlsx")
    assert url.endswith("TDoc_List_RAN2%23129.xlsx")


def test_update_selects_new_and_recent_meetings() -> None:
    entries = filter_meetings(parse_listing((FIXTURES / "listing.html").read_text(), "https://example.test/root/"), "125")
    selected = select_meetings_for_update(entries, {"TSGR2_125"}, 1)
    assert [entry.name for entry in selected] == ["TSGR2_125bis", "TSGR2_126"]
    selected = select_meetings_for_update(entries, {entry.name for entry in entries}, 1)
    assert [entry.name for entry in selected] == ["TSGR2_126"]
