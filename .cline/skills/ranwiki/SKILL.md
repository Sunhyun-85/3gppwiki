---
name: ranwiki
description: Research and incrementally update the shared local 3GPP RAN knowledge base using deterministic JSON CLI commands. Use for RAN2/RAN3/RAN4 meeting questions, Chair Notes, TDocs, Rel-20, 6G, topic history, working-group outcomes, provenance, or explicit corpus update requests.
---

# Use the local 3GPP RAN knowledge base

This skill requires no external LLM API. Cline performs synthesis; `ranwiki` performs local retrieval, parsing, indexing, and explicit repository updates.

For user-facing operation, installation, and prompt examples, consult `docs/user-guide-ko.md`, `docs/closed-network-install-ko.md`, and `docs/cline-prompt-guide-ko.md`.

## Evidence rules

1. Do not answer a 3GPP meeting-material question from model memory first. Run local retrieval with `--json`.
2. Prefer Chair Notes for working-group outcomes. Only an explicitly parsed `AGREEMENT` or `CONCLUSION` supports a claim that the group decided something.
3. A company TDoc is a proposal unless Chair Notes independently record the group outcome. Never promote a proposal to an agreement.
4. Preserve `group`, `meeting`, `agenda`, `tdoc_id`, source/company, source file, locator, and source URL/path in citations.
5. If indexed evidence is insufficient, state that limitation instead of filling the gap from memory.
6. Keep all access inside the closed network. Do not call a paid API or download a local LLM.

## Research workflow

Start with:

`./ranwiki status --json`

Then search:

`./ranwiki search "<topic>" --group RAN2 --scope ALL --limit 20 --json`

For cross-meeting evolution:

`./ranwiki trace "<topic>" --group RAN2 --scope ALL --json`

For actual group decisions or open points:

`./ranwiki outcomes "<topic>" --group RAN2 --types AGREEMENT,CONCLUSION,FFS --json`

Retrieve supporting sources as needed:

`./ranwiki chair-notes <meeting> --group RAN2 --agenda <agenda> --json`

`./ranwiki tdoc <R2-number> --group RAN2 --json`

Use `--full` on `tdoc` only when the compact excerpt is insufficient. Answer in the user's language and cite the evidence fields above.

For a company-specific question, add `--company <company>` to search, retrieve the important TDocs, and separately check Chair Notes/outcomes.

## Explicit update workflow

Only update when the user asks to refresh/update or says a new meeting occurred:

1. `./ranwiki status --json`
2. `./ranwiki update --group RAN2 --json`
3. `./ranwiki status --json`
4. `./ranwiki audit --group RAN2 --json`
5. Run one representative search or meeting lookup.
6. Report new meetings, checked/downloaded/changed files, indexed records, Chair Notes availability, warnings/errors, and latest indexed meeting.

Updates are incremental. Do not delete raw data, rebuild the database as a shortcut, or modify the web UI.
If an update reports a repository error, note that safely downloaded files are still extracted/indexed; report both the partial progress and the failure.

## Adding RAN3 or RAN4

Do not merely change an FTP path or assume RAN2 layout. When explicitly asked to enable another group:

1. Inspect its actual reachable repository tree and representative Chair Notes, TDoc lists, agenda, reports, and TDoc packages.
2. Extend the group adapter/configuration and generic shared schema.
3. Add offline group-specific fixtures and tests for meeting and TDoc naming.
4. Back up the SQLite database before any migration.
5. Enable and ingest only the selected meeting range, then verify RAN2 web/API compatibility.

Use native TDoc prefixes (`R2-`, `R3-`, `R4-`). Reuse the shared database; do not create a parallel application.
