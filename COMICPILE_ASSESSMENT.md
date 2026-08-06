# ComicPile assessment of CBL-ReadingLists

Assessment generated from repository commit `64ad2b8` (July 19, 2026).

## Executive summary

CBL-ReadingLists is a useful curated seed for ComicPile reading-list memberships, event/crossover discovery, series continuity, and candidate chronology edges. It is not a dependency-graph dataset: CBL encodes flat ordered lists, while phases, optionality, parallel lanes, hard/soft dependencies, and provenance are usually implicit in filenames, directories, README files, or inferred from issue metadata.

Recommendation: ingest it as a provenance-preserving, source-specific collection of alternate orders. Do not treat any order as authoritative canon without retaining its source and confidence.

## Repository-wide statistics

| Metric | Count |
|---|---:|
| CBL files | 1,702 |
| Book entries | 336,324 |
| Unique Comic Vine issue IDs/raw identities | 76,709 |
| Unique raw series names | 7,847 |
| XML parse errors | 0 |
| Duplicate comic identities within one list | 53 |
| Entries without usable Comic Vine issue ID | 18 |
| Entries containing Metron IDs | 44 |

Top-level file counts: Marvel 1,118; DC 471; Other 48; Valiant 13; Boom 9; Dark Horse 9; Image 9; IDW 7; Zenescope 6; Vertigo 4; Archie Comics 3; Dynamite 2; Avatar Press, Chaos Comics, and Rebellion 1 each.

Most-referenced raw series: The Amazing Spider-Man (394 lists), Fantastic Four (319), Daredevil (257), Captain America (254), Avengers (248), Wolverine (227), and X-Men (222).

The largest list has 3,180 entries: `Marvel/Master Reading Order/CBRO - With Events/[Marvel] Marvel Master Reading Order Part #10 (WEB-CBRO).cbl`.

## Practical CBL schema

```xml
<ReadingList>
  <Name>display name</Name>
  <NumIssues>58</NumIssues>
  <Books>
    <Book Series="Silver Surfer" Number="34" Volume="1987" Year="1990">
      <Database Name="cv" Series="3857" Issue="32433" />
    </Book>
  </Books>
</ReadingList>
```

Observed elements and attributes are `ReadingList`, `Name`, `NumIssues`, `Books`, `Book`, `Series`, `Number`, `Volume`, `Year`, `Format`, `Database`, `Name`, `Series`, and `Issue`. Comic Vine (`cv`) is dominant, but Metron also occurs. Some entries have no database or use `Name="none"`.

Document position is the only consistently encoded ordering signal. Linear orders are supported; phases, optional issues, core/tie-in status, parallel lanes, branching, hard dependencies, soft dependencies, and multiple valid orderings are not explicit CBL concepts. They must be inferred from alternate files and metadata.

## Provenance

Provenance appears in directory names, filenames, and directory README files. Common traditions include CBRO, LoCG, Marvel Guides, CMRO, Comic Book Herald, Reddit, UXRO, and Official. It is not reliably stored inside each XML file; 435 files have no detected source marker.

Examples of competing traditions include CBRO versus LoCG Infinity Gauntlet files, CBRO versus LoCG Valiant events, and alternate Fantastic Four, Massive-Verse, Avengers, and Thunderbolts lists.

## Infinity Gauntlet

Dedicated files:

| Source | Entries |
|---|---:|
| CBRO | 51 |
| LoCG | 58 |

The two lists share 47 Comic Vine issue IDs. Their shared issues have no reversed pairwise ordering disagreements. The disagreement is primarily scope: CBRO includes some interstitial issues such as Sleepwalker #6, while LoCG extends the Silver Surfer and Warlock and the Infinity Watch aftermath through Silver Surfer #66 and Warlock and the Infinity Watch #6.

Likely inferred phases are: Silver Surfer/Thanos Quest prelude; Infinity Gauntlet #1–6 main event; Quasar, Doctor Strange, Hulk, Spider-Man, Cloak and Dagger, and Sleepwalker tie-ins; and Silver Surfer/Warlock and the Infinity Watch aftermath. These classifications are inferences, not XML fields.

The complete machine-readable comparison is in `infinity_gauntlet_comparison.json`.

## Data-quality findings

- 18 entries lack usable Comic Vine issue IDs.
- 44 entries contain Metron IDs, mostly alongside Comic Vine IDs.
- Half issues use values such as `½`; negative issues use `-1`.
- One Fantastic Four/Comic Book Herald entry has a blank issue number and `Year="0"`.
- One Wonder Woman entry uses `Database Name="none" Series="none" Issue="none"`.
- 53 duplicate identities occur within individual lists.
- Very large master orders are useful chronology inputs but may be poor single dependency graphs.
- Publication-order lists, character chronologies, event lists, simplified lists, and “with events” master lists are mixed together.
- Official checklist images are present but are not machine-readable memberships.

## ComicPile integration

Persist the original repository path, filename, display name, source evidence, repository commit SHA, import time, content hash, ordinal position, raw fields, all external IDs, resolved ComicPile ID, confidence, inferred role, and manual overrides.

Recommended logical tables are `reading_lists`, `reading_list_sources`, `external_comics`, `reading_list_memberships`, and `comic_identity_overrides`. Index memberships by list/ordinal, external ID, resolved comic ID, source, and inferred role.

Import flow: update repository; record commit; hash and detect changed files; parse safely; validate; normalize; preserve raw XML; resolve exact external IDs; fuzzy-match unresolved entries for review; compare alternate orders; generate candidate edges; and preserve manual decisions across imports.

For candidate graph edges, calculate pairwise ordering agreement across lists containing both comics. High-agreement edges supported by independent source traditions and series continuity can become hard candidates; conflicting or sparse evidence should remain soft or parallel. Detect cycles with strongly connected components and downgrade the least-supported edge rather than silently sorting contradictions away. Every inferred edge should retain supporting lists, sources, confidence, and reasons.

## Files created for the analysis

- `parse_cbl.py`: dependency-free CBL parser.
- `analyze_cbl_repo.py`: repository-wide statistics and exhaustive JSON report generator.
- `compare_reading_lists.py`: alternate-order comparison tool.
- `infinity_gauntlet_comparison.json`: compact case-study output.

The exhaustive `report.json` is generated locally by `analyze_cbl_repo.py`; it is intentionally not committed because it is approximately 126 MB and exceeds GitHub's normal 100 MB file limit.
