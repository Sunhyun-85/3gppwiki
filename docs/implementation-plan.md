# Concise implementation plan

1. Foundation: typed configuration, provenance-first SQLite/FTS5 schema,
   resilient link-directory discovery, CLI, logging, and offline fixtures.
2. Ingestion: idempotent manifest comparison, streamed downloads, SHA-256,
   format extractors, TDoc-list normalization, and structured JSON outputs.
3. Chair Notes: document-order parsing into agenda sections and strictly typed
   outcomes, plus explicit TDoc links and manual sample audits.
4. Retrieval: hierarchical Chair Notes/agenda/title search before TDoc passages,
   BM25 filters, topic chronology, compact provenance-bearing results.
5. Service: six small MCP tools with local-only binding and Korean-default
   grounded assistant instructions.
6. Operations: zero-LLM local search UI, persistent Compose volumes,
   Tailscale-only access/optional Serve HTTPS, then end-to-end retrieval audits.
   Open WebUI remains an optional future provider integration.
