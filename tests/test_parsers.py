from ran2wiki.parsers.chair_notes import parse_blocks
from ran2wiki.parsers.common import extract_tdoc_ids, normalize_tdoc_id
from ran2wiki.parsers.tdoc_list import normalize_columns, parse_rows


def test_tdoc_number_parsing() -> None:
    assert normalize_tdoc_id("R2_2501234 revision") == "R2-2501234"
    assert extract_tdoc_ids("See R2-2501234 and R2 2505678; again R2-2501234") == ["R2-2501234", "R2-2505678"]


def test_column_normalization_and_rows() -> None:
    assert normalize_columns(["TDoc No", "Document title", "Source/Company", "AI"])[2] == "source_company"
    rows = [["cover"], ["TDoc No", "Document title", "Source/Company", "AI", "WI/SI", "Result"],
            ["R2-2501234", "Dynamic UE capability", "Samsung", "7.3", "NR_cap", "noted"]]
    parsed = parse_rows(rows)
    assert parsed[0].tdoc_id == "R2-2501234"
    assert parsed[0].source_company == "Samsung"
    assert parsed[0].status == "noted"


def test_chair_notes_sections_references_and_outcomes() -> None:
    sections = parse_blocks([
        "7.3 Dynamic UE capability",
        "Samsung presented R2-2501234. Ericsson commented in R2_2505678.",
        "Agreement: The UE reports the supported mode.",
        "FFS: Whether the indication is per cell.",
        "8.1 Mobility",
        "Conclusion - discussion will continue.",
        "Agreements | This belongs to the second section.",
    ])
    assert sections[0].tdoc_ids == ["R2-2501234", "R2-2505678"]
    assert [o.outcome_type for o in sections[0].outcomes] == ["AGREEMENT", "FFS"]
    assert sections[1].outcomes[0].outcome_type == "CONCLUSION"
    assert sections[1].outcomes[1].outcome_type == "AGREEMENT"


def test_grouped_agreements_end_at_blank() -> None:
    sections = parse_blocks([
        "10.4 Mobility",
        "Agreements",
        "1 Study robust mobility.",
        "- Minimize interruption.",
        "",
        "R2-2501234 Next contribution",
    ])
    assert [item.text for item in sections[0].outcomes] == [
        "1 Study robust mobility.", "- Minimize interruption."
    ]
    assert "R2-2501234 Next contribution" in sections[0].discussion


def test_ffs_inside_agreement_is_dual_typed_but_proposal_is_not() -> None:
    sections = parse_blocks([
        "10.4 Mobility", "Agreements", "Study signaling; FFS exact encoding.", "",
        "Proposal 1: FFS whether this proposal is useful.",
    ])
    assert [item.outcome_type for item in sections[0].outcomes] == ["AGREEMENT", "FFS"]
    assert "Proposal 1" in sections[0].discussion[-1]
