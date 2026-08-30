# ECDICT source snapshot

The upstream ECDICT artifact is `raw/stardict.7z`, downloaded from the
`skywind3000/ECDICT` repository at commit `bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b`.
The archive contains the upstream `stardict.csv` export. The upstream license
is retained in [`LICENSE`](LICENSE).

`ecdict.sqlite` is the application-facing local projection. It keeps the
fields needed by Lyric Vocabulary Builder in a smaller `dictionary` table and
is intentionally ignored by Git because of its size.

The reproducible comparison command is:

```text
python3 processing/scripts/compare_ecdict.py \
  sources/ecdict/ecdict.sqlite /path/to/extracted/stardict.csv
```

The comparison report is maintained in [`docs/source-comparison.md`](../../docs/source-comparison.md).
