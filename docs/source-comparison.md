# Dictionary source comparison

Snapshot date: 2026-08-30.

## ECDICT

The local snapshot uses the upstream `skywind3000/ECDICT` archive at commit
`bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b`. The original archive and MIT
license are stored under [`sources/ecdict`](../sources/ecdict/).

The upstream archive contains 3,402,564 CSV rows. The local SQLite projection
contains 3,402,222 rows. Comparing the local `dictionary` table with the
upstream `stardict.csv`, after accounting for CSV line-ending encoding,
empty/default values, and the local field names, shows:

- 3,401,746 exact word-key matches.
- 818 upstream keys are absent verbatim and 476 local keys are extra. All 818
  are explained by leading-apostrophe cleanup; no word remains missing after
  removing that leading apostrophe. The cleanup also collapses 342 variants
  into already-existing keys.
- 2,028 exact-key rows have substantive field differences. By local field,
  these are: `phonetic` 1,489; `definition` 241; `translation` 314; `pos` 122;
  `collins_star` 92; `bnc_rank` 146; `frq_rank` 122; `forms` 605.

The local ECDICT work therefore includes schema projection, null/default and
line-ending normalization, leading-apostrophe key cleanup, form-field
normalization, and content changes in 2,028 matched rows. The exact samples and counts
can be regenerated with `processing/scripts/compare_ecdict.py`.

## 2ndLA

The local snapshot uses `2ndLA/english-phrases` commit
`4362d151decd8fd92e511bdd2cda31efbe63c8eb`. The ten original list files and
CC BY-SA 4.0 license are stored under [`sources/2ndla`](../sources/2ndla/).

The ten lists contain 17,216 non-filtered source lines. The local pipeline:

- applies NFKC normalization, trimming and whitespace collapsing;
- converts curly apostrophes to straight apostrophes and case-folds keys;
- retains 2–5-token phrases with supported punctuation;
- retains `sb.`/`sth.` placeholders and ellipsis templates, normalizing
  ellipses to `...` in canonical phrases;
- expands the single slash template `expend time/money on sb.` into
  `expend time on sb.` and `expend money on sb.`; and
- rejects phrases longer than five tokens or with unsupported punctuation;
- deduplicates phrases while preserving source-list membership and source
  forms; and
- adds stable IDs, provenance URLs, license, phrase type and translation
  status fields.

This produces 8,207 retained candidates and 268 rejected lines. The original
filter rejects 191 overlong phrases and 27 non-phrase/shape cases: five contain
unsupported commas and 22 are single-token words or compounds. A subsequent
review pass corrected 42 malformed candidates to stable canonical phrases and
explicitly excluded 39 candidates whose intended correction was ambiguous;
some of those decisions apply to more than one raw source line.
The decisions are recorded in
[`review-decisions.json`](../sources/2ndla/review-decisions.json).
Re-running
`processing/scripts/prepare_2ndla.py --review-file sources/2ndla/review-decisions.json`
against `sources/2ndla/raw` reproduces the checked-in `entries.jsonl`,
`rejected.json` and manifest byte-for-byte. The first review pass processed 81
of the old 435-row backlog: 42 entries were corrected and 39 were explicitly
excluded. The remaining 354 review rows are still
unchanged and are not eligible for later SQLite import until resolved.
