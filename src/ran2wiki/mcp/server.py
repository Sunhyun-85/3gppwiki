from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

try:
    from mcp.server.mcpserver import MCPServer  # MCP Python SDK 2.x
except ImportError:  # pragma: no cover - retained for distro-packaged 1.x SDKs
    from mcp.server.fastmcp import FastMCP as MCPServer

from ran2wiki.config import load_config
from ran2wiki.db import connect
from ran2wiki.search import KnowledgeService

mcp = MCPServer("RAN2 Wiki")


@contextmanager
def service() -> Iterator[KnowledgeService]:
    config = load_config(os.getenv("RAN2WIKI_CONFIG", "config.yaml"))
    with connect(config.paths.database) as db:
        yield KnowledgeService(db)


@mcp.tool()
def search_ran2(query: str, scope: str = "ALL", meeting: str | None = None, agenda: str | None = None,
                company: str | None = None, from_meeting: str | None = None,
                to_meeting: str | None = None, limit: int = 10, group: str = "RAN2",
                release: str | None = None) -> list[dict]:
    """Search local RAN2 evidence. Returns meeting/TDoc/source provenance; scope is REL20, 6G, or ALL."""
    with service() as api:
        return api.search_ran2(query, scope, meeting, from_meeting, to_meeting, agenda, company, limit, group, release)


@mcp.tool()
def get_tdoc(tdoc_id: str, group: str = "RAN2") -> dict | None:
    """Get one R2 TDoc with metadata, content, relationships, and source provenance."""
    with service() as api:
        return api.get_tdoc(tdoc_id, group)


@mcp.tool()
def get_meeting(meeting: str, group: str = "RAN2") -> dict | None:
    """Get a RAN2 meeting summary and agenda; accepts 131bis or TSGR2_131bis."""
    with service() as api:
        return api.get_meeting(meeting, group)


@mcp.tool()
def get_chair_notes(meeting: str, agenda: str | None = None, group: str = "RAN2") -> list[dict]:
    """Get Chair Notes sections and explicitly typed outcomes for a meeting/agenda."""
    with service() as api:
        return api.get_chair_notes(meeting, agenda, group)


@mcp.tool()
def trace_topic(query: str, group: str = "RAN2", scope: str = "ALL") -> list[dict]:
    """Trace TDocs and Chair Notes outcomes for a topic in chronological meeting order."""
    with service() as api:
        return api.trace_topic(query, group=group, scope=scope)


@mcp.tool()
def find_agreements(query: str, outcome_type: str = "ALL", limit: int = 20, group: str = "RAN2") -> list[dict]:
    """Search only explicit AGREEMENT, CONCLUSION, or FFS Chair Notes outcomes."""
    with service() as api:
        return api.find_agreements(query, outcome_type, limit, group)


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host=os.getenv("RAN2WIKI_MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("RAN2WIKI_MCP_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
