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
- retains only 2–5-token phrases with supported punctuation;
- rejects slash templates, `sb`/`sth` placeholders and unsupported forms;
- deduplicates phrases while preserving source-list membership and source
  forms; and
- adds stable IDs, provenance URLs, license, phrase type and translation
  status fields.

This produces 7,200 retained candidates and 1,612 rejected lines. Re-running
`processing/scripts/prepare_2ndla.py` against `sources/2ndla/raw` reproduces
the checked-in `entries.jsonl`, `rejected.json` and manifest byte-for-byte.
The separate translation layer contains 6,765 generated full-dataset entries
and 435 entries marked for review; it is kept outside the source candidate
table.
