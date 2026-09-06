from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GroupAdapter:
    """Stable group identity; repository layout is configured only after inspection."""

    name: str
    meeting_prefix: str
    tdoc_prefix: str
    enabled: bool = False

    def meeting_name(self, value: str) -> str:
        value = value.strip()
        return value if value.upper().startswith(self.meeting_prefix) else f"{self.meeting_prefix}{value}"

    def normalize_tdoc_id(self, value: str) -> str:
        match = re.search(rf"\b{re.escape(self.tdoc_prefix)}[-_ ]?(\d{{7}})\b", value, re.I)
        return f"{self.tdoc_prefix}-{match.group(1)}" if match else value.upper().replace("_", "-")


_GROUPS = {
    "RAN2": GroupAdapter("RAN2", "TSGR2_", "R2", True),
    # Deliberately no repository paths: inspect each real closed-network tree before enabling.
    "RAN3": GroupAdapter("RAN3", "TSGR3_", "R3"),
    "RAN4": GroupAdapter("RAN4", "TSGR4_", "R4"),
}


def get_group_adapter(name: str) -> GroupAdapter:
    try:
        return _GROUPS[name.upper()]
    except KeyError as exc:
        raise ValueError(f"unsupported group: {name}; choose RAN2, RAN3, or RAN4") from exc


def supported_groups() -> tuple[GroupAdapter, ...]:
    return tuple(_GROUPS.values())
