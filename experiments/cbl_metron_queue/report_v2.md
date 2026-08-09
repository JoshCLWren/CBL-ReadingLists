# CBL / ComicPile diagnostic pass v2

This pass consumed existing `queue_matches.json` and `cbl_cache.json`; it did not rerun corpus parsing or identity matching.

## File relevance diagnosis
- CBL files parsed: 1702
- Files with >=1 accepted issue match: 574
- Files with >=2 accepted issue matches: 501
- Files with >=2 matched threads: 339
- Focused lists with >=2 matches: 62
- Broad chronology/master lists with matches: 460
- Files with zero accepted matches: 1128

The original “Relevant CBL files: 1702” was actually the total number of parsed files, taken from the cache, not files containing accepted matches.

## Dependency diagnosis
The original implementation generated all ordered issue pairs within each file, but required at least two forward supporting files and >=75% agreement. It did not calculate thread-collapsed transitions or parallel lanes. The new diagnostics report co-occurrence and conflict counts for ±1, ±3, and ±10 windows, plus full pairwise evidence only for focused lists <=250 entries.

## Exploratory results
- Repeated-order candidates (window 3): 31
- Independent-support candidates (window 3): 118
- Conflicting-order candidates (window 3): 1
- Thread transition candidates: 483
- Parallel-lane candidates: 23

Concrete examples are in `examples_v2.json`. Full evidence and stage counts are in the JSON diagnostics artifacts.
