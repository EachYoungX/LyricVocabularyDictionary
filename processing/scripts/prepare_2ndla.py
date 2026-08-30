#!/usr/bin/env python3
"""Download and normalize the phrase lists published by 2ndLA.

The output is a phrase-candidate dataset only.  It deliberately contains no
translation inferred from ECDICT and no automatically generated word pairs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


REPOSITORY = "2ndLA/english-phrases"
RAW_BASE_URL = "https://raw.githubusercontent.com/2ndLA/english-phrases/main/lists"
SOURCE_BASE_URL = "https://github.com/2ndLA/english-phrases/blob/main/lists"
LISTS = (
    "junior",
    "senior",
    "cet4",
    "cet6",
    "tem4",
    "tem8",
    "gre",
    "ielts",
    "toefl",
    "npee",
)
ALLOWED_PHRASE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9'’.-]*(?: [A-Za-z0-9][A-Za-z0-9'’.-]*)+$"
)
ELLIPSIS_SENTINEL = "\ue000"


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "IyricVocabularyBuilder/phrase-import"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def normalize_phrase(line: str) -> str | None:
    phrase = normalize_text(line)
    validation_phrase = phrase.replace("...", " ")
    validation_phrase = re.sub(r"\s+", " ", validation_phrase).strip()
    phrase = re.sub(r"\s+", " ", phrase)
    if not phrase or not ALLOWED_PHRASE.fullmatch(validation_phrase):
        return None
    if not 2 <= phrase_token_count(phrase) <= 5:
        return None
    return phrase.casefold().replace("’", "'")


def phrase_token_count(phrase: str) -> int:
    phrase = phrase.replace("…", " ").replace("...", " ")
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.-]*", phrase))


def normalize_text(line: str) -> str:
    protected = line.replace("…", ELLIPSIS_SENTINEL)
    phrase = unicodedata.normalize("NFKC", protected).strip()
    phrase = re.sub(r"\s+", " ", phrase)
    phrase = phrase.replace(ELLIPSIS_SENTINEL, "...")
    return re.sub(r"\.{4,}", "...", phrase)


def normalize_phrases(line: str) -> list[str]:
    """Normalize a line, expanding a single slash template into alternatives."""
    phrase = normalize_text(line)
    if not phrase:
        return []
    if "/" not in phrase:
        normalized = normalize_phrase(phrase)
        return [normalized] if normalized is not None else []

    slash_tokens = [token for token in phrase.split(" ") if token.count("/") == 1]
    if phrase.count("/") != 1 or len(slash_tokens) != 1:
        return []
    token = slash_tokens[0]
    alternatives = token.split("/")
    expanded = [phrase.replace(token, alternative, 1) for alternative in alternatives]
    normalized = [normalize_phrase(candidate) for candidate in expanded]
    return [candidate for candidate in normalized if candidate is not None]


def load_review_decisions(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {"corrections": {}, "exclusions": {}}
    decisions = json.loads(path.read_text(encoding="utf-8"))
    return {
        "corrections": decisions.get("corrections", {}),
        "exclusions": decisions.get("exclusions", {}),
    }


def build_entries(
    source_dir: Path | None, review_decisions: dict[str, dict[str, str]] | None = None
) -> tuple[list[dict], Counter, list[dict], dict[str, str]]:
    review_decisions = review_decisions or {"corrections": {}, "exclusions": {}}
    memberships: defaultdict[str, set[str]] = defaultdict(set)
    source_forms: defaultdict[str, set[str]] = defaultdict(set)
    raw_counts: Counter = Counter()
    raw_hashes: dict[str, str] = {}
    rejected: list[dict] = []

    for list_name in LISTS:
        if source_dir is None:
            content = fetch(f"{RAW_BASE_URL}/{list_name}.txt")
            raw_hashes[list_name] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        else:
            source_path = source_dir / f"{list_name}.txt"
            raw_bytes = source_path.read_bytes()
            raw_hashes[list_name] = hashlib.sha256(raw_bytes).hexdigest()
            content = raw_bytes.decode("utf-8-sig")
        lines = content.splitlines()
        raw_counts[list_name] = len(lines)
        for line_number, line in enumerate(lines, start=1):
            phrases = normalize_phrases(line)
            if not phrases:
                if line.strip():
                    rejected.append({"list": list_name, "line": line_number, "value": line.strip()})
                continue
            for phrase in phrases:
                if phrase in review_decisions["exclusions"]:
                    rejected.append(
                        {
                            "list": list_name,
                            "line": line_number,
                            "value": line.strip(),
                            "reason": review_decisions["exclusions"][phrase],
                            "reviewAction": "EXCLUDE",
                        }
                    )
                    continue
                canonical_phrase = review_decisions["corrections"].get(phrase, phrase)
                memberships[canonical_phrase].add(list_name)
                source_forms[canonical_phrase].add(
                    re.sub(r"\s+", " ", unicodedata.normalize("NFKC", line).strip())
                )

    entries = []
    for phrase in sorted(memberships):
        lists = sorted(memberships[phrase], key=lambda name: (LISTS.index(name), name))
        entries.append(
            {
                "id": f"2ndla:{phrase}",
                "canonicalPhrase": phrase,
                "tokenCount": phrase_token_count(phrase),
                "phraseType": "SOURCE_CANDIDATE",
                "source": REPOSITORY,
                "sourceForms": sorted(source_forms[phrase]),
                "sourceLists": lists,
                "sourceUrls": [f"{SOURCE_BASE_URL}/{name}.txt" for name in lists],
                "license": "CC BY-SA 4.0",
                "translationStatus": "PENDING",
                "meaningZh": None,
            }
        )
    return entries, raw_counts, rejected, raw_hashes


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    return {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def select_pilot(entries: list[dict], size: int, index: int = 0, count: int = 1) -> list[dict]:
    """Select a deterministic, evenly distributed sample partition."""
    if size <= 0 or not entries:
        return []
    if count <= 0 or not 0 <= index < count:
        raise ValueError("pilot index must be within pilot count")
    total_size = size * count
    if total_size >= len(entries):
        return entries
    indices = [round(position * (len(entries) - 1) / (total_size - 1)) for position in range(total_size)]
    return [entries[position] for position in indices[index * size : (index + 1) * size]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, help="Use checked-out list files instead of downloading them.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pilot-size", type=int, default=300)
    parser.add_argument("--source-commit", default="main")
    parser.add_argument("--pilot-index", type=int, default=0)
    parser.add_argument("--pilot-count", type=int, default=1)
    parser.add_argument("--pilot-output", default="translation-pilot-input.jsonl")
    parser.add_argument("--exclude-file", type=Path)
    parser.add_argument("--review-file", type=Path, help="Apply reviewed corrections and exclusions.")
    args = parser.parse_args()

    review_decisions = load_review_decisions(args.review_file)
    entries, raw_counts, rejected, raw_hashes = build_entries(args.source_dir, review_decisions)
    write_jsonl(args.output_dir / "entries.jsonl", entries)
    excluded_ids = read_ids(args.exclude_file)
    pilot_entries = [entry for entry in entries if entry["id"] not in excluded_ids]
    write_jsonl(
        args.output_dir / args.pilot_output,
        select_pilot(pilot_entries, args.pilot_size, args.pilot_index, args.pilot_count),
    )
    (args.output_dir / "rejected.json").write_text(
        json.dumps(rejected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "source": REPOSITORY,
                "sourceRepository": "https://github.com/2ndLA/english-phrases",
                "sourceCommit": args.source_commit,
                "license": "CC BY-SA 4.0",
                "licenseFile": "LICENSE",
                "lists": list(LISTS),
                "rawDirectory": "raw",
                "rawFiles": {
                    f"raw/{name}.txt": raw_hashes[name] for name in LISTS
                },
                "rawLineCounts": raw_counts,
                "uniqueEntries": len(entries),
                "rejectedEntries": len(rejected),
                "normalization": {
                    "case": "casefold",
                    "whitespace": "collapse",
                    "tokenCount": "2-5",
                    "excluded": ["more than 5 tokens", "unsupported punctuation/shape"],
                    "slashExpansion": "A single slash token is expanded into one entry per alternative.",
                    "placeholders": "sb./sth. placeholders and unicode ellipsis templates are retained.",
                },
                "reviewDecisions": str(args.review_file) if args.review_file else None,
                "translationPolicy": "meaningZh is populated only by an explicit phrase translation step; ECDICT is not used to infer phrases.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
