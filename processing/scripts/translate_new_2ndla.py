#!/usr/bin/env python3
"""Translate source candidates not yet present in the full translation output.

This creates a machine-translation draft for the newly admitted candidates.
Existing translation rows, including REVIEW_REQUIRED rows, are copied without
any changes. The source phrase is translated as a complete phrase; common
source placeholders are expanded only in the request sent to the translator.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


API_URL = "https://api.mymemory.translated.net/get"
MANUAL_TRANSLATIONS = {
    "do sb. credit": "使某人增光；对某人有利",
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def translation_query(phrase: str) -> str:
    query = phrase
    query = query.replace("sb.'s", "someone's").replace("sb.s", "someone's")
    query = query.replace("sth.'s", "something's").replace("sth.s", "something's")
    query = query.replace("sb.", "someone").replace("sth.", "something").replace("sp.", "somewhere")
    return query


def translate(phrase: str, email: str | None = None) -> str:
    query = translation_query(phrase)
    params = urllib.parse.urlencode(
        {"q": query, "langpair": "en|zh-CN", **({"de": email} if email else {})},
        quote_via=urllib.parse.quote,
    )
    request = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={"User-Agent": "LyricVocabularyDictionary/2ndla-translation"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload.get("responseData", {}).get("translatedText", "").strip()
    if not result or result.casefold() == query.casefold():
        raise ValueError("translator returned no translated text")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("sources/2ndla/entries.jsonl"))
    parser.add_argument("--existing", type=Path, default=Path("translations/2ndla/translation-full-output.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("translations/2ndla/translation-full-output.jsonl"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--email", help="Optional contact email used by MyMemory for quota attribution.")
    args = parser.parse_args()

    source_rows = load_jsonl(args.source)
    existing_rows = load_jsonl(args.existing)
    existing_by_id = {row["id"]: row for row in existing_rows}
    new_rows = [row for row in source_rows if row["id"] not in existing_by_id]
    translated: dict[str, str] = {}
    failures: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(translate, row["canonicalPhrase"], args.email): row for row in new_rows}
        for index, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            try:
                translated[row["id"]] = future.result()
            except Exception as error:  # Keep one failed request from losing the batch.
                failures[row["id"]] = str(error)
            if index % 50 == 0 or index == len(new_rows):
                print(f"processed={index}/{len(new_rows)} translated={len(translated)} failed={len(failures)}", flush=True)

    output_rows = []
    for row in source_rows:
        if row["id"] in existing_by_id:
            output_rows.append(existing_by_id[row["id"]])
            continue
        meaning = translated.get(row["id"], "")
        output_rows.append(
            {
                "id": row["id"],
                "canonicalPhrase": row["canonicalPhrase"],
                "meaningZh": meaning,
                "usageNoteZh": "",
                "translationStatus": "GENERATED" if meaning else "REVIEW_REQUIRED",
                "confidence": "MEDIUM" if meaning else "LOW",
            }
        )
    for row in output_rows:
        manual_meaning = MANUAL_TRANSLATIONS.get(row["canonicalPhrase"])
        if manual_meaning and row["translationStatus"] != "GENERATED":
            row["meaningZh"] = manual_meaning
            row["translationStatus"] = "GENERATED"
            row["confidence"] = "MEDIUM"
    args.output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in output_rows) + "\n",
        encoding="utf-8",
    )
    print(f"existing={len(existing_rows)} new={len(new_rows)} translated={len(translated)} failed={len(failures)} output={len(output_rows)}")
    if failures:
        for row in new_rows:
            if row["id"] in failures:
                print(f"failed {row['canonicalPhrase']!r}: {failures[row['id']]}")


if __name__ == "__main__":
    main()
