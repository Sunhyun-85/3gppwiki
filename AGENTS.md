# Repository guidance

- Preserve source provenance from discovery through retrieval.
- Never promote a proposal to an agreement. Only Chair Notes outcomes explicitly parsed as AGREEMENT or CONCLUSION support group decisions.
- Keep ingestion deterministic and offline-testable.
- Raw downloaded files are immutable inputs; extracted representations belong under `data/extracted`.
- Do not add embeddings or a vector database in v0.1.

## Cline integration

- Cline must follow the local skill at `.cline/skills/ranwiki/SKILL.md` for 3GPP RAN research and explicit updates.
- Prefer `ranwiki ... --json`; do not scrape the web UI or query SQLite directly.
