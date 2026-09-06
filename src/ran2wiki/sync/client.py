from __future__ import annotations

import logging
import time
from collections import deque
from urllib.parse import urlsplit

import httpx

from ran2wiki.models import RemoteEntry
from ran2wiki.sync.discovery import filter_meetings, parse_listing

LOG = logging.getLogger(__name__)


class RepositoryClient:
    def __init__(self, timeout: int = 60) -> None:
        self.http = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "ran2wiki/0.1 (personal research indexer)"})

    def close(self) -> None:
        self.http.close()

    def listing(self, url: str) -> list[RemoteEntry]:
        response = self.http.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and not response.text.lstrip().startswith("<"):
            raise ValueError(f"expected directory HTML from {url}, got {content_type}")
        return parse_listing(response.text, str(response.url))

    def discover_meetings(self, base_url: str, start: str, end: str | None = None,
                          group: str = "RAN2") -> list[RemoteEntry]:
        return filter_meetings(self.listing(base_url.rstrip("/") + "/"), start, end, group)

    def walk_primary_files(self, meeting_url: str, max_depth: int = 3) -> list[RemoteEntry]:
        """Follow only known meeting-material directories; never crawl outside the meeting."""
        allowed = {"agenda", "docs", "documents", "inbox", "chair_notes", "tdoclists", "report", "lsin", "lsout", "zips", "pdfs"}
        origin_path = urlsplit(meeting_url).path.rstrip("/") + "/"
        queue = deque([(meeting_url.rstrip("/") + "/", 0)])
        seen: set[str] = set()
        files: list[RemoteEntry] = []
        while queue:
            url, depth = queue.popleft()
            if url in seen or depth > max_depth:
                continue
            seen.add(url)
            for entry in self.listing(url):
                if not urlsplit(entry.url).path.startswith(origin_path):
                    continue
                if entry.is_directory:
                    if entry.name.casefold() in allowed:
                        queue.append((entry.url.rstrip("/") + "/", depth + 1))
                else:
                    files.append(entry)
        return files

    def fetch(self, url: str) -> bytes:
        error: Exception | None = None
        attempts = 5
        for attempt in range(attempts):
            try:
                response = self.http.get(url)
                response.raise_for_status()
                return response.content
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 and exc.response.status_code < 500:
                    raise
                error = exc
            except httpx.TransportError as exc:
                error = exc
            LOG.warning("download attempt %d/%d failed for %s: %s", attempt + 1, attempts, url, error)
            if attempt < attempts - 1:
                time.sleep(min(2 ** attempt, 8))
        assert error is not None
        raise error
