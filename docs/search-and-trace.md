# Search and topic trace behavior

`search_ran2` is hierarchical. It searches final Chair Notes sections first,
then TDoc titles/body text, while retaining evidence type, meeting, agenda,
company, status, local source file, official URL, and locator where available.
Chair evidence is not automatically an agreement: explicit outcomes remain in
the separate `outcome_type` field.

Filters include scope (`REL20`, `6G`, or `ALL`), exact meeting, meeting-number
range, agenda, company, and result limit. FTS5/BM25 performs lexical ranking;
there are no embeddings or vector database in v0.1.

`trace_topic` groups evidence chronologically using the parsed meeting number
and `bis` ordering. Each meeting has three distinct arrays:

- `chair_evidence`: matching final Chair Notes sections;
- `tdocs`: matching contributions and their company/status metadata;
- `outcomes`: explicit matching AGREEMENT, CONCLUSION, or FFS records.

Agreement matching requires every query term to occur in the outcome text. This
reduces generic 6G outcomes leaking into a specific query such as `6G mobility`.
The assistant should use English technical terms for local retrieval even when
the user asks in Korean, then synthesize the response in Korean.

## Real validation snapshot

Selective ingestion of official TDoc lists and final Chair Notes through RAN2
#135 produced 8,217 TDoc records, 1,902 6G-classified records, 979 Chair Notes
sections, and 1,151 typed outcomes. A `6G mobility` trace returned chronological
evidence for #131bis, #132, #133, #134, and #135. It did not label discussion-only
meetings as agreements.

