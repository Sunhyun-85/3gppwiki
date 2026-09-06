from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class FileKind(StrEnum):
    CHAIR_NOTES = "chair_notes"
    AGENDA = "agenda"
    TDOC_LIST = "tdoc_list"
    TDOC = "tdoc"
    REPORT = "report"
    LS_IN = "ls_in"
    LS_OUT = "ls_out"
    METADATA = "metadata"
    OTHER = "other"


class Classification(StrEnum):
    REL20 = "REL20"
    SIX_G = "6G"
    REL20_AND_6G = "REL20_AND_6G"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RemoteEntry:
    name: str
    url: str
    is_directory: bool
    modified_at: datetime | None = None
    size: int | None = None
    kind: FileKind = FileKind.OTHER


def meeting_sort_key(name: str) -> tuple[int, int, str]:
    normalized = __import__("re").sub(r"^TSGR[234]_", "", name, flags=__import__("re").I).lower()
    digits = "".join(c for c in normalized if c.isdigit())
    number = int(digits) if digits else -1
    suffix_rank = 1 if "bis" in normalized else 0
    return number, suffix_rank, normalized
