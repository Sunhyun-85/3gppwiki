from __future__ import annotations

from ran2wiki.config import ClassificationConfig
from ran2wiki.models import Classification


def classify_text(text: str, work_item: str | None, config: ClassificationConfig) -> Classification:
    haystack = f"{text} {work_item or ''}".casefold()
    rel20 = any(term.casefold() in haystack for term in (*config.rel20_keywords, *config.rel20_work_items))
    six_g = any(term.casefold() in haystack for term in (*config.six_g_keywords, *config.six_g_work_items))
    if rel20 and six_g:
        return Classification.REL20_AND_6G
    if six_g:
        return Classification.SIX_G
    if rel20:
        return Classification.REL20
    return Classification.UNKNOWN if not haystack.strip() else Classification.OTHER

