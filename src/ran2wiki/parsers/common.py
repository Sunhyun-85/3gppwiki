from __future__ import annotations

import re

TDOC_PATTERN = re.compile(r"\b(R[234])[-_ ]?(\d{7})\b", re.IGNORECASE)


def normalize_tdoc_id(value: object) -> str | None:
    match = TDOC_PATTERN.search(str(value or ""))
    return f"{match.group(1).upper()}-{match.group(2)}" if match else None


def extract_tdoc_ids(text: str) -> list[str]:
    return list(dict.fromkeys(f"{match.group(1).upper()}-{match.group(2)}" for match in TDOC_PATTERN.finditer(text)))
