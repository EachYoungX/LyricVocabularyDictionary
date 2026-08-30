# 2ndLA phrase candidate dataset

This directory contains a normalized, phrase-candidate extraction from
[2ndLA/english-phrases](https://github.com/2ndLA/english-phrases).

The source project provides phrase lists without translations. `entries.jsonl`
therefore contains candidate phrases and source provenance only; it is not a
claim that every retained line is a fixed expression. A phrase must
be explicitly translated before `meaningZh` can be populated. ECDICT is a
word-level dictionary and is intentionally not used to infer phrase meanings.

Files:

- `raw/*.txt`: the ten upstream list files at the pinned source commit.
- `entries.jsonl`: deduplicated 2–5 token phrase entries, including
  `sb.`/`sth.` placeholders and ellipsis templates.
- `review-decisions.json`: reviewed corrections and explicit exclusions for
  malformed candidates.
- `translation-pilot-input.jsonl`: first pilot batch for explicit translation.
- `manifest.json`: source, normalization, and license metadata.
- `rejected.json`: source lines excluded by the conservative filter.

The source data is licensed under CC BY-SA 4.0. Keep this notice and the
source attribution when redistributing the derived dataset.
The complete license text is retained in [`LICENSE`](LICENSE), and the raw
file hashes are recorded in `manifest.json`.

The source preparation keeps phrases longer than five tokens out, expands the
source line `expend time/money on sb.` into two entries, applies the reviewed
corrections in `review-decisions.json`, and excludes candidates whose intended
correction cannot be established. The current normalized set has 8,013 entries
and 452 rejected source lines. The full translation output has 8,013 generated
rows and no remaining review rows. In the final review pass, 44
incomplete-structure rows were corrected or completed and 89 were explicitly
excluded.
