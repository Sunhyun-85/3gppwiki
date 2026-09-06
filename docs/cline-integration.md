# Cline integration

The current application has one shared path: downloader/extractors and TDoc-list/Chair Notes parsers write `data/db/ran2wiki.db`; `KnowledgeService` serves that database to the existing web API, MCP server, and CLI. The additive Cline integration invokes the same service through the `ranwiki` CLI alias.

The shared schema stores group identity on each meeting (and sync run). TDocs, files, documents, agenda items, and Chair Notes inherit it through their meeting foreign key. Existing rows migrate to `RAN2`; existing `ran2wiki` commands and web endpoints remain valid.

## Cline examples

```bash
./ranwiki search "6G mobility" --group RAN2 --scope 6G --limit 20 --json
./ranwiki trace "6G mobility" --group RAN2 --scope 6G --json
./ranwiki outcomes "6G mobility" --group RAN2 --types AGREEMENT,CONCLUSION,FFS --json
```

For a company proposal:

```bash
./ranwiki search "dynamic UE capability" --group RAN2 --company Samsung --json
./ranwiki tdoc R2-2501234 --group RAN2 --json
./ranwiki chair-notes 131bis --group RAN2 --json
```

The second command above is only an interface example; use TDoc IDs returned by the first command rather than assuming that example exists in the local corpus.

For an explicit refresh request:

```bash
./ranwiki status --json
./ranwiki update --group RAN2 --json
./ranwiki status --json
./ranwiki audit --group RAN2 --json
```

RAN3 and RAN4 adapters are registered but disabled. Their repository locations are intentionally absent until their real closed-network structures have been inspected and tested.
