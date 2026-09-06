from __future__ import annotations

import json
import os
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlparse

from ran2wiki.config import load_config
from ran2wiki.db import connect
from ran2wiki.search import KnowledgeService


def _one(params: dict[str, list[str]], name: str, default: str | None = None) -> str | None:
    values = params.get(name)
    return values[0].strip() if values and values[0].strip() else default


class RAN2WikiHandler(BaseHTTPRequestHandler):
    server_version = "RAN2Wiki/0.1"

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _index(self) -> None:
        body = files("ran2wiki.web").joinpath("index.html").read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTP handler API
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._index()
            return
        if parsed.path == "/healthz":
            self._json({"status": "ok"})
            return
        if not parsed.path.startswith("/api/"):
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        params = parse_qs(parsed.query)
        config = load_config(os.getenv("RAN2WIKI_CONFIG", "config.yaml"))
        try:
            with connect(config.paths.database) as db:
                service = KnowledgeService(db)
                result = self._dispatch(parsed.path[5:], params, service)
            self._json(result)
        except (ValueError, sqlite3.OperationalError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception:
            self.log_exception()
            self._json({"error": "request failed"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _dispatch(self, endpoint: str, params: dict[str, list[str]], service: KnowledgeService) -> object:
        limit = min(int(_one(params, "limit", "20") or "20"), 100)
        if endpoint == "status":
            return service.status()
        if endpoint == "meetings":
            return service.list_meetings(limit)
        if endpoint == "search":
            query = _one(params, "q")
            if not query:
                raise ValueError("q is required")
            return service.search_ran2(
                query, _one(params, "scope", "ALL") or "ALL", _one(params, "meeting"),
                _one(params, "from_meeting"), _one(params, "to_meeting"),
                _one(params, "agenda"), _one(params, "company"), limit,
            )
        if endpoint == "meeting":
            return service.get_meeting(_one(params, "id") or "")
        if endpoint == "tdoc":
            return service.get_tdoc(_one(params, "id") or "")
        if endpoint == "chair-notes":
            return service.get_chair_notes(_one(params, "meeting") or "", _one(params, "agenda"))
        if endpoint == "agreements":
            query = _one(params, "q")
            if not query:
                raise ValueError("q is required")
            return service.find_agreements(query, _one(params, "type", "ALL") or "ALL", limit)
        if endpoint == "trace":
            query = _one(params, "q")
            if not query:
                raise ValueError("q is required")
            return service.trace_topic(query)
        raise ValueError("unknown API endpoint")

    def log_exception(self) -> None:
        import traceback
        traceback.print_exc()


def main() -> None:
    host = os.getenv("RAN2WIKI_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("RAN2WIKI_WEB_PORT", "8080"))
    print(f"RAN2 Wiki web UI listening on http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), RAN2WikiHandler).serve_forever()


if __name__ == "__main__":
    main()
