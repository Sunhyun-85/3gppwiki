from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from ran2wiki.models import FileKind, RemoteEntry, meeting_sort_key

MEETING_RE = re.compile(r"^TSGR[234]_(\d+)(bis|-e)?$", re.IGNORECASE)
TDOC_RE = re.compile(r"^R[234][-_ ]\d{7}(?:[-_].*)?\.zip$", re.IGNORECASE)
SIZE_RE = re.compile(r"(?P<value>[\d.,]+)\s+(?P<unit>[KMGT]?B)\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b(20\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2})\b")


class _ListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None


def parse_size(value: str) -> int | None:
    match = SIZE_RE.search(value)
    if not match:
        return None
    raw = match.group("value")
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    multiplier = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return round(float(raw) * multiplier[match.group("unit").upper()])


def classify_path(path: str) -> FileKind:
    lower = path.lower()
    name = path.rstrip("/").rsplit("/", 1)[-1]
    if "chair_notes" in lower and name.endswith((".docx", ".zip", ".pdf")):
        return FileKind.CHAIR_NOTES
    if "tdoc_list" in lower or "/tdoclists/" in lower:
        return FileKind.TDOC_LIST
    if TDOC_RE.match(name):
        return FileKind.TDOC
    if "/agenda/" in lower:
        return FileKind.AGENDA
    if "/report/" in lower:
        return FileKind.REPORT
    if "/lsin/" in lower:
        return FileKind.LS_IN
    if "/lsout/" in lower:
        return FileKind.LS_OUT
    return FileKind.OTHER


def encoded_url(base_url: str, href: str) -> str:
    """Join a listing href while preserving reserved characters in filenames."""
    # Directory listings sometimes expose a literal '#' in spreadsheet names.
    # Encode it before urljoin/urlsplit can interpret it as a fragment marker.
    safe_href = href.replace("#", "%23")
    joined = urljoin(base_url.rstrip("/") + "/", safe_href)
    parts = urlsplit(joined)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), parts.query, ""))


def parse_listing(html: str, base_url: str) -> list[RemoteEntry]:
    parser = _ListingParser()
    parser.feed(html)
    entries: list[RemoteEntry] = []
    for href, text in parser.links:
        if not text or text in {"..", "Parent Directory"} or href.startswith(("?", "#")):
            continue
        is_dir = href.endswith("/") or "." not in text.rsplit("/", 1)[-1]
        position = html.find(f'href="{href}"')
        if position < 0:
            position = html.find(href)
        row_start = html.rfind("<tr", 0, position) if position >= 0 else -1
        row_end = html.find("</tr>", position) if position >= 0 else -1
        context = html[row_start:row_end] if row_start >= 0 and row_end >= 0 else ""
        date_match = DATE_RE.search(context)
        modified = None
        if date_match:
            modified = datetime.strptime(" ".join(date_match.groups()), "%Y/%m/%d %H:%M")
        entries.append(RemoteEntry(
            name=text.rstrip("/"),
            url=encoded_url(base_url, href),
            is_directory=is_dir,
            modified_at=modified,
            size=None if is_dir else parse_size(context),
            kind=classify_path(urljoin(base_url + "/", href)),
        ))
    return entries


def discover_meetings(html: str, base_url: str, start: str, end: str | None = None,
                      group: str = "RAN2") -> list[RemoteEntry]:
    lower = meeting_sort_key(start)
    upper = meeting_sort_key(end) if end else None
    prefix = {"RAN2": "TSGR2_", "RAN3": "TSGR3_", "RAN4": "TSGR4_"}[group.upper()]
    meetings = [e for e in parse_listing(html, base_url) if e.is_directory and e.name.upper().startswith(prefix)]
    return sorted(
        (e for e in meetings if meeting_sort_key(e.name) >= lower and (upper is None or meeting_sort_key(e.name) <= upper)),
        key=lambda e: meeting_sort_key(e.name),
    )


def filter_meetings(entries: list[RemoteEntry], start: str, end: str | None = None,
                    group: str = "RAN2") -> list[RemoteEntry]:
    """Filter an already parsed repository listing to the configured meeting range."""
    lower = meeting_sort_key(start)
    upper = meeting_sort_key(end) if end else None
    prefix = {"RAN2": "TSGR2_", "RAN3": "TSGR3_", "RAN4": "TSGR4_"}[group.upper()]
    return sorted(
        (entry for entry in entries if entry.is_directory and entry.name.upper().startswith(prefix)
         and meeting_sort_key(entry.name) >= lower
         and (upper is None or meeting_sort_key(entry.name) <= upper)),
        key=lambda entry: meeting_sort_key(entry.name),
    )
