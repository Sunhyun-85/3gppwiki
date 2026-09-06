# MCP and Web UI validation

Validation date: 2026-09-03.

The MCP server was started on localhost using Streamable HTTP. An independent
MCP SDK 2.x client completed the protocol handshake, listed exactly six tools,
and invoked every tool successfully against the real local database:

- `search_ran2`
- `get_tdoc`
- `get_meeting`
- `get_chair_notes`
- `trace_topic`
- `find_agreements`

Every invocation returned `is_error=false` and structured content. This tests
the wire protocol rather than calling Python service methods directly.

The Docker image built successfully. Open WebUI v0.6.42 and the RAN2 MCP service
started through Compose, Open WebUI returned HTTP 200 on `127.0.0.1:3000`, and
the Open WebUI container resolved/reached `http://ran2wiki-mcp:8000/mcp` over
the private Compose network. The MCP service has no host port mapping.

LLM-backed answer generation is intentionally outside the zero-LLM deployment.
The MCP contract is validated independently and remains available for a future
MCP-capable client chosen by the user.
Persistent deployment also requires a generated `WEBUI_SECRET_KEY`. The first
browser user becomes the Open WebUI administrator; that administrator must add
the MCP Streamable HTTP connection using the internal URL above and attach it
to the chat/model. These account/secret steps are intentionally not automated
with invented credentials.
