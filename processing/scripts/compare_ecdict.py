#!/usr/bin/env python3
"""Compare the app-facing ECDICT SQLite projection with an upstream export."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter
from pathlib import Path


LOCAL_COLUMNS = (
    "phonetic",
    "definition",
    "translation",
    "pos",
    "collins_star",
    "bnc_rank",
    "frq_rank",
    "forms",
)
UPSTREAM_COLUMNS = (
    "phonetic",
    "definition",
    "translation",
    "pos",
    "collins",
    "bnc",
    "frq",
    "exchange",
)


def canonical_word(word: str) -> str:
    """Match the local import's leading-apostrophe cleanup for diagnostics."""
    return word.lstrip("'").casefold()


def normalize_upstream(row: dict[str, str]) -> tuple:
    values = [row[column] or None for column in UPSTREAM_COLUMNS]
    for index in (0, 1, 2, 3, 7):
        if values[index] is not None:
            values[index] = values[index].replace("\\r", "\r").replace("\\n", "\n")
    # The local projection stores ECDICT's default numeric zeros as NULL.
    for index in (4, 5, 6):
        if values[index] is not None:
            values[index] = int(values[index])
            if values[index] == 0:
                values[index] = None
    return tuple(values)


def normalize_local(values: tuple) -> tuple:
    normalized = list(values)
    for index in (0, 1, 2, 3, 7):
        if normalized[index] == "":
            normalized[index] = None
    for index in (4, 5, 6):
        if normalized[index] == 0:
            normalized[index] = None
    return tuple(normalized)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("local_db", type=Path)
    parser.add_argument("upstream_csv", type=Path)
    parser.add_argument("--sample-size", type=int, default=10)
    args = parser.parse_args()

    connection = sqlite3.connect(args.local_db)
    local = connection.cursor()
    local_words = {row[0] for row in local.execute("select word from dictionary")}
    exact_missing: list[str] = []
    field_differences: list[tuple[str, tuple, tuple]] = []
    field_difference_counts: Counter[str] = Counter()
    field_samples: dict[str, tuple[str, object, object]] = {}
    upstream_words: set[str] = set()
    rows = 0

    with args.upstream_csv.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            rows += 1
            word = row["word"]
            upstream_words.add(word)
            expected = normalize_upstream(row)
            actual_row = local.execute(
                "select " + ",".join(LOCAL_COLUMNS) + " from dictionary where word=?",
                (word,),
            ).fetchone()
            if actual_row is None:
                exact_missing.append(word)
                continue
            actual = normalize_local(tuple(actual_row))
            if actual != expected:
                field_differences.append((word, actual, expected))
                for index, (local_value, upstream_value) in enumerate(zip(actual, expected)):
                    if local_value != upstream_value:
                        field = f"{LOCAL_COLUMNS[index]} (upstream {UPSTREAM_COLUMNS[index]})"
                        field_difference_counts[field] += 1
                        field_samples.setdefault(field, (word, local_value, upstream_value))

    exact_extra = local_words - upstream_words
    normalized_local = {}
    normalized_upstream = {}
    for word in local_words:
        normalized_local.setdefault(canonical_word(word), []).append(word)
    for word in upstream_words:
        normalized_upstream.setdefault(canonical_word(word), []).append(word)
    apostrophe_pairs = [
        (key, sorted(normalized_local[key]), sorted(normalized_upstream[key]))
        for key in sorted(set(normalized_local) & set(normalized_upstream))
        if set(normalized_local[key]) != set(normalized_upstream[key])
    ]
    true_missing = [word for word in exact_missing if canonical_word(word) not in normalized_local]

    print(f"upstream_rows={rows}")
    print(f"local_rows={len(local_words)}")
    print(f"exact_word_matches={rows - len(exact_missing)}")
    print(f"exact_missing={len(exact_missing)} sample={exact_missing[:args.sample_size]}")
    print(f"exact_extra={len(exact_extra)} sample={sorted(exact_extra)[:args.sample_size]}")
    print(f"leading_apostrophe_pairs={len(apostrophe_pairs)} sample={apostrophe_pairs[:args.sample_size]}")
    print(f"true_missing_after_normalization={len(true_missing)} sample={true_missing[:args.sample_size]}")
    print(f"field_differences_on_exact_matches={len(field_differences)}")
    print(f"field_difference_counts={dict(field_difference_counts)}")
    for field, (word, local_value, upstream_value) in sorted(field_samples.items()):
        print(f"field_difference field={field!r} word={word!r} local={local_value!r} upstream={upstream_value!r}")


if __name__ == "__main__":
    main()
