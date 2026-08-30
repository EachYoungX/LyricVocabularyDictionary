# 2ndLA phrase candidate dataset

This directory contains a normalized, phrase-candidate extraction from
[2ndLA/english-phrases](https://github.com/2ndLA/english-phrases).

The source project provides phrase lists without translations. `entries.jsonl`
therefore contains candidate phrases and source provenance only; it is not a
claim that every retained line is a fixed expression. A phrase must
be explicitly translated before `meaningZh` can be populated. ECDICT is a
word-level dictionary and is intentionally not used to infer phrase meanings.

Files:

- `entries.jsonl`: deduplicated 2–5 token phrase entries.
- `translation-pilot-input.jsonl`: first pilot batch for explicit translation.
- `manifest.json`: source, normalization, and license metadata.
- `rejected.json`: source lines excluded by the conservative filter.

The source data is licensed under CC BY-SA 4.0. Keep this notice and the
source attribution when redistributing the derived dataset.
