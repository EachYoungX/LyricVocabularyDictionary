#!/usr/bin/env python3
"""Validate a phrase translation JSONL against its source JSONL."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: expected JSON object")
        rows.append(value)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("translated", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    source = load(args.source)
    translated = load(args.translated)
    expected = source[: args.limit] if args.limit is not None else source
    if len(expected) != len(translated):
        raise SystemExit(f"row-count-mismatch expected={len(expected)} actual={len(translated)}")

    for index, (expected_row, translated_row) in enumerate(zip(expected, translated), start=1):
        for field in ("id", "canonicalPhrase"):
            if expected_row.get(field) != translated_row.get(field):
                raise SystemExit(
                    f"key-mismatch row={index} field={field} "
                    f"expected={expected_row.get(field)!r} actual={translated_row.get(field)!r}"
                )
        required = {"id", "canonicalPhrase", "meaningZh", "usageNoteZh", "translationStatus", "confidence"}
        missing = required.difference(translated_row)
        if missing:
            raise SystemExit(f"missing-fields row={index}: {sorted(missing)}")

    statuses = Counter(row["translationStatus"] for row in translated)
    print(f"valid rows={len(translated)} statuses={dict(sorted(statuses.items()))}")


if __name__ == "__main__":
    main()
