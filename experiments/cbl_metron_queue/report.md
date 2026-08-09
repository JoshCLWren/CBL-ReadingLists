# CBL / ComicPile queue experiment

## Executive summary
Offline analysis of `comicpile-reading-data.json` against `1702` CBL files. Metron was not run because no credentials/config were available.

## Summary table

- ComicPile threads: 166
- ComicPile issues: 3332
- Threads matched to any CBL: 98
- Issues matched exactly: 20096
- Issues matched fuzzily: 88
- Issues matched through Metron: 0
- Unresolved issues: 873
- Ambiguous issues: 77
- Relevant CBL files: 1702
- Candidate hard dependencies: 0
- Candidate soft dependencies: 0
- Candidate parallel lanes: 0 (not enough conservative lane evidence)

## Export statistics
Statuses: {'completed': 42, 'active': 124}. Threads with no issue records: 5. Threads with issue records: 161. Duplicate titles and unusual numbers are preserved in `stats.json`/source-derived records.

## Top overlapping CBL lists
- `Marvel/Teams/X-Men/WEB-CBRO/[Marvel] X-Men with events (WEB-CBRO).cbl` — 704 issues / 15 threads
- `Marvel/Teams/X-Men/WEB-CBRO/[Marvel] X-Men no events (WEB-CBRO).cbl` — 483 issues / 9 threads
- `Marvel/Master Reading Order/CBRO - With Events/[Marvel] Marvel Master Reading Order Part #05 (WEB-CBRO).cbl` — 322 issues / 13 threads
- `Marvel/Creator Runs/[Marvel] [1975-1991] Complete X-Titles by Chris Claremont.cbl` — 285 issues / 6 threads
- `Marvel/Master Reading Order/CBRO - With Events/[Marvel] Marvel Master Reading Order Part #04 (WEB-CBRO).cbl` — 276 issues / 10 threads
- `Marvel/Master Reading Order/CMRO/Core/[Marvel] CMRO Core Reading Order-Part 10.cbl` — 260 issues / 14 threads
- `Marvel/Teams/unsorted/X-Men/X-Men - Part 004 (Blue - Gold).cbl` — 232 issues / 7 threads
- `Marvel/Master Reading Order/CBRO/[Marvel] Marvel Master Reading Order Part #05 (WEB-CBRO).cbl` — 213 issues / 10 threads
- `Marvel/Master Reading Order/CMRO/Expanded/[Marvel] CMRO Expanded Reading Order-Part 20.cbl` — 212 issues / 18 threads
- `Marvel/Teams/unsorted/X-Men/X-Men - Part 006.cbl` — 203 issues / 11 threads
- `Marvel/Master Reading Order/CMRO/Main/[Marvel] CMRO Main Reading Order-Part 12.cbl` — 198 issues / 8 threads
- `Marvel/Teams/unsorted/X-Men/X-Men - Part 003.cbl` — 197 issues / 4 threads
- `Marvel/Teams/X-Men/WEB-CBRO/[Marvel] X-Men Krakoa Era with events (WEB-CBRO).cbl` — 196 issues / 8 threads
- `Marvel/Teams/X-Men/Age of Krakoa/Age of Krakoa - Single List/[X-Men Krakoa] [2019-Present] The Age of Krakoa.cbl` — 196 issues / 8 threads
- `Marvel/Master Reading Order/CBRO/[Marvel] Marvel Master Reading Order Part #04 (WEB-CBRO).cbl` — 195 issues / 7 threads
- `Marvel/Master Reading Order/CMRO/Main/[Marvel] CMRO Main Reading Order-Part 13.cbl` — 189 issues / 17 threads
- `Marvel/Master Reading Order/CMRO/Core/[Marvel] CMRO Core Reading Order-Part 11.cbl` — 186 issues / 8 threads
- `Marvel/Master Reading Order/CMRO/Essential/[Marvel] CMRO Essential Reading Order-Part 02.cbl` — 181 issues / 12 threads
- `Marvel/Teams/X-Men/WEB-CBRO/[Marvel] X-Men Krakoa Era no events (WEB-CBRO).cbl` — 174 issues / 8 threads
- `Marvel/Teams/unsorted/X-Men/X-Men - Part 005.cbl` — 170 issues / 9 threads

## Interpretation
Accepted matches are direct normalized title/issue evidence or constrained fuzzy evidence; each retains CBL path, ordinal, and external IDs. Dependencies are candidates only and weight repeated list co-occurrence/order, but this first pass does not infer hard gates or parallel lanes.

## Metron and next experiment
`metron_pending.json` contains unresolved issue identities for a credentialed follow-up. Metron could add canonical IDs and disambiguate relaunches; ComicPile should later store stable external IDs, series identity, volume/year, issue identity, source provenance, and explicit dependency confidence.

## Data quality
The export uses a `jsonb_pretty` wrapper and has no named reading orders; queue order therefore comes from `queue_position` as requested. See `unresolved.json` for records needing review.
