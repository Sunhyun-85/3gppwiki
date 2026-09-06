# RAN2 Wiki

Local-first 3GPP RAN2 Rel-20 / 6G knowledge base for a small Linux server. The
local machine downloads, extracts, indexes, and serves grounded evidence. The
default system requires no LLM, API key, billing account, or paid service.

## Current implementation status

Phase 0 and Phase 1 are complete. Phase 2 includes an incremental manifest,
atomic/hash-verified downloads, preserved prior versions, deterministic
document extraction, real TDoc-list parsing/indexing, and operational CLI
commands. Chair Notes parsing, FTS search/topic trace, MCP, and a private
zero-LLM search UI are also present; complete archive ingestion remains
operational work. Open WebUI is retained as an opt-in future integration.

Phase 3 indexes one canonical final/EoM main Chair Notes source per meeting to
avoid treating superseded interim notes as current conclusions. Grouped
agreement bodies, explicit conclusions, agreement-scoped FFS, noted items, and
Chair Notes-to-TDoc references are stored separately with source locators.

Phase 4/5 hierarchical search and chronological topic tracing are operational.
See [search and trace behavior](docs/search-and-trace.md).

`ran2wiki update` discovers all configured official meeting directories,
downloads every new non-empty meeting, rechecks the newest configured meetings,
and then extracts and indexes changes. Empty advance meeting directories are
ignored until materials appear.

## Cline / machine-readable CLI

The packaged `ranwiki` command is a backward-compatible alias of `ran2wiki`.
On this PEP 668-managed host, use the checked-in `./ranwiki` launcher without
changing system Python.
Cline uses the native project skill in `.cline/skills/ranwiki/SKILL.md` and the
same database/service layer as the existing web UI. No paid API or LLM is
needed by this integration. See [Cline integration](docs/cline-integration.md).

Korean operation documents:

- [사용자 설명서](docs/user-guide-ko.md)
- [폐쇄망 설치 및 이관 가이드](docs/closed-network-install-ko.md)
- [Cline 프롬프트 가이드와 예시](docs/cline-prompt-guide-ko.md)
- [v0.1.0 릴리스 노트](docs/release-notes-v0.1.0.md)
- [GitHub Release 배포 가이드](docs/github-release-ko.md)

Build a credential/data-free source release with:

```bash
python3 scripts/build_release.py
(cd dist && sha256sum -c SHA256SUMS)
```

For the initial long backfill, `docker compose --profile jobs up -d --build
ran2wiki-update` runs the same update independently of the login/session.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,ingest,mcp]'
cp config.example.yaml config.yaml
ran2wiki init
ran2wiki status
ran2wiki serve-web
pytest
```

See [the data-source investigation](docs/data-source-investigation.md) for the
verified upstream layout and [the implementation plan](docs/implementation-plan.md).
