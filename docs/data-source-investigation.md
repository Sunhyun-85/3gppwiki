# Official RAN2 data-source investigation

Investigation date: 2026-09-03. The observations below come from the official
3GPP file repository, not inferred paths.

## Host environment

- Ubuntu-compatible Linux, x86-64, Python 3.14.4.
- Docker 29.6.1 and Docker Compose 5.2.0 are installed.
- Tailscale 1.102.2 is installed. It was not connected/configured during this
  inspection, so cross-device reachability cannot yet be claimed.
- The `sqlite3` shell is absent, but Python's SQLite library has FTS5 enabled.

## Observed repository structure

The RAN2 root is `https://www.3gpp.org/ftp/tsg_ran/WG2_RL2/`. Modern meeting
directories use `TSGR2_<number>`, with suffix variants such as
`TSGR2_131bis`; older names and layouts vary and are intentionally not assumed.

RAN2#131bis (October 2025) exposes these top-level directories:

- `Agenda/`
- `Docs/`
- `Inbox/`
- `Invitation/`
- `LSin/`
- `LSout/`
- `Report/`

`Docs/` contains finalized `R2-YYNNNNN.zip` contributions and a meeting TDoc
spreadsheet such as `TDoc_List_Meeting_RAN2#129.xlsx`. `Inbox/` contains late
or working TDocs plus `Chair_Notes/`, `Drafts/`, and `Email_Discussions/`.
`Report/` may contain a single ZIP (for example `R2-2508002.zip` at #131bis).
Older meetings may have `Tdoclists/`, nested `Documents/Docs`, `Zips/`, or
`pdfs/`; discovery therefore follows links and classifies them instead of
constructing one rigid path.

The observed #131bis Chair Notes folder contained:

- `R2_131bis_ChairNotes_25-10-12.docx`
- `R2_131bis_Schedule v05.docx`
- a topic-owner notes DOCX

The main Chair Notes file is a real OOXML DOCX. Its document XML is large and
contains paragraph styles, tables, hyperlinks, and split text runs (including
split meeting/TDoc identifiers), so extraction must concatenate runs in
document order and include tables; plain XML substring matching is inadequate.

A live recursive metadata walk on 2026-09-03 found 1,341 primary meeting files:
1,240 TDoc ZIP links, 24 agenda/schedule versions, one TDoc-list workbook, and
74 Chair Notes/session-note versions. The latter include interim timestamps and
`R2_131bis_ChairNotes_25-10-17_17-00_final.zip`; ingestion must retain versions
and prefer an explicitly final/EoM source for outcomes while keeping earlier
versions as raw provenance.

The #131bis workbook downloaded successfully through its percent-encoded URL
(280,829 bytes at download time) and yielded 1,142 TDoc metadata rows.

Directory listings expose link name, directory/file distinction, displayed
modification time, and displayed size. These are sufficient for cheap change
detection, followed by SHA-256 after download. Displayed sizes use localized
decimal commas and KB units, so the parser normalizes them cautiously.

## Scope boundary

The official 3GPP portal records Rel-20 as created on 2024-03-14. RAN2#125 was
held in March 2024, making #125 the evidence-based default starting meeting to
retain Rel-20 planning context. This does **not** imply every #125+ document is
Rel-20.

Official 3GPP planning material says RAN2/3/4 6G studies start in Q4 2025.
RAN2#131bis (October 2025) is therefore the first regular RAN2 meeting at that
boundary, but classification remains content/agenda/WI driven. The configured
start remains #125 so Rel-20 planning and precursor relationships are not lost.

## Access caveat discovered

The `ftp.3gpp.org` host redirects to `www.3gpp.org`. For filenames containing
literal `#` (notably TDoc spreadsheets), the redirect currently emits an
unescaped `#`, turning the remainder into a URL fragment and causing failure.
The client must retain encoded paths, avoid inventing alternate filenames, and
report access failures. Direct encoded requests to `www.3gpp.org` are verified
to work, including the #131bis spreadsheet. This behavior is covered by URL
construction and live parser tests.

## Final Chair Notes validation

The official `R2_131bis_ChairNotes_25-10-17_17-00_final.zip` is 345,395 bytes
by listing metadata and contains one final DOCX. The deterministic parser
indexed 189 agenda-like sections, 46 substantive AGREEMENT statements, two
CONCLUSION statements, three FFS statements occurring inside agreed blocks,
160 NOTED markers, and 1,068 links to known TDocs. Proposals containing the word
FFS outside an agreed/concluded block are not promoted to meeting-level FFS.

The document frequently represents outcomes as an `Agreements` heading followed
by numbered/bulleted blocks, rather than `Agreement: text` on one line. The
parser therefore uses a blank-line-bounded grouped-outcome state. A remaining
heuristic limitation is that unstyled numbered prose can occasionally resemble
an agenda heading; source locators are retained and future parser refinement
should combine DOCX paragraph styles with the agenda workbook structure.

## Sources

- https://www.3gpp.org/ftp/tsg_ran/WG2_RL2/TSGR2_131bis/
- https://www.3gpp.org/ftp/tsg_ran/WG2_RL2/TSGR2_131bis/Inbox/
- https://www.3gpp.org/ftp/tsg_ran/WG2_RL2/TSGR2_131bis/Inbox/Chair_Notes/
- https://www.3gpp.org/ftp/tsg_ran/WG2_RL2/TSGR2_129/Docs
- https://portal.3gpp.org/desktopmodules/Release/ReleaseDetails.aspx?releaseId=195
