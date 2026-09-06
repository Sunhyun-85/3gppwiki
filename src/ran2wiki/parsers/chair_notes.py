from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ran2wiki.parsers.common import extract_tdoc_ids

AGENDA_RE = re.compile(r"^\s*(?:agenda(?: item)?\s*)?(\d+(?:\.\d+){0,4})[\s:.-]+(.+)$", re.IGNORECASE)
OUTCOME_RE = re.compile(
    r"^\s*(?:[•*-]\s*)?(Agreements?|Conclusions?|FFS|Postponed|Noted)\s*(?:[:.|-]\s*|$)(.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Outcome:
    outcome_type: str
    text: str
    locator: str


@dataclass
class ChairSection:
    agenda: str
    title: str
    discussion: list[str] = field(default_factory=list)
    tdoc_ids: list[str] = field(default_factory=list)
    outcomes: list[Outcome] = field(default_factory=list)
    locator: str = ""


def parse_blocks(blocks: list[str]) -> list[ChairSection]:
    sections: list[ChairSection] = []
    current: ChairSection | None = None
    grouped_outcome: str | None = None
    for ordinal, raw in enumerate(blocks, 1):
        text = re.sub(r"\s+", " ", raw).strip()
        if not text:
            grouped_outcome = None
            continue
        if grouped_outcome and current is not None:
            for tdoc_id in extract_tdoc_ids(text):
                if tdoc_id not in current.tdoc_ids:
                    current.tdoc_ids.append(tdoc_id)
            current.outcomes.append(Outcome(grouped_outcome, text, f"block:{ordinal}"))
            if "FFS" in text.upper():
                current.outcomes.append(Outcome("FFS", text, f"block:{ordinal}"))
            continue
        agenda = AGENDA_RE.match(text)
        if agenda and len(agenda.group(2)) > 2:
            grouped_outcome = None
            current = ChairSection(agenda=agenda.group(1), title=agenda.group(2), locator=f"block:{ordinal}")
            sections.append(current)
            continue
        if current is None:
            continue
        for tdoc_id in extract_tdoc_ids(text):
            if tdoc_id not in current.tdoc_ids:
                current.tdoc_ids.append(tdoc_id)
        outcome = OUTCOME_RE.match(text)
        if outcome:
            raw_kind = outcome.group(1).upper()
            kind = raw_kind[:-1] if raw_kind in {"AGREEMENTS", "CONCLUSIONS"} else raw_kind
            body = outcome.group(2).strip()
            if not body and raw_kind in {"AGREEMENTS", "CONCLUSIONS"}:
                grouped_outcome = kind
            else:
                current.outcomes.append(Outcome(kind, body or text, f"block:{ordinal}"))
                if kind in {"AGREEMENT", "CONCLUSION"} and "FFS" in (body or text).upper():
                    current.outcomes.append(Outcome("FFS", body or text, f"block:{ordinal}"))
        else:
            current.discussion.append(text)
    return sections


def docx_blocks(path: str | Path) -> list[str]:
    """Extract paragraphs and tables in approximate OOXML document order."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(path)
    blocks: list[str] = []
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            blocks.append(Paragraph(child, document).text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            for row in table.rows:
                blocks.append(" | ".join(cell.text for cell in row.cells))
    return blocks


def parse_docx(path: str | Path) -> list[ChairSection]:
    return parse_blocks(docx_blocks(path))
