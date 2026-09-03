#!/usr/bin/env python3
"""Build the application-facing SQLite release database."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


FUNCTION_WORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "if",
    "in", "into", "is", "it", "of", "on", "or", "that", "the", "than",
    "to", "up", "was", "when", "with",
}
PARTICLES = {
    "about", "apart", "around", "away", "back", "down", "off", "on",
    "out", "over", "through", "up",
}
PREPOSITIONS = {
    "about", "against", "at", "by", "for", "from", "in", "into", "of",
    "on", "over", "to", "with",
}

SLOT_RULES = {
    "PERSON": (1, 4),
    "THING": (1, 5),
    "POSSESSIVE": (1, 4),
    "REFLEXIVE": (1, 3),
    "VERB": (1, 3),
    "GERUND": (1, 3),
    "OBJECT": (1, 4),
    "GENERIC": (1, 4),
}


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def unescape_text(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("\\r", "\r").replace("\\n", "\n")


def integer_value(value: str | None) -> int | None:
    if not value:
        return None
    parsed = int(value)
    return parsed or None


def boolean_value(value: str | None) -> int | None:
    if not value:
        return None
    if value in {"0", "1"}:
        return int(value)
    return None


def normalized_word(value: str) -> str:
    # Keep the established local ECDICT cleanup for leading apostrophes while
    # retaining normal capitalization and applying NOCASE uniqueness in SQL.
    return value.lstrip("'")


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE word_entry (
            id              INTEGER PRIMARY KEY,
            word            TEXT COLLATE NOCASE NOT NULL UNIQUE,
            phonetic        TEXT,
            definition_en   TEXT,
            translation_zh  TEXT,
            pos_profile     TEXT,
            collins_star    INTEGER,
            oxford_core     INTEGER,
            tags            TEXT,
            bnc_rank        INTEGER,
            coca_rank       INTEGER,
            morphology      TEXT
        );

        CREATE TABLE phrase_entry (
            id                   INTEGER PRIMARY KEY,
            source_pattern       TEXT NOT NULL,
            canonical_pattern    TEXT NOT NULL,
            definition_en        TEXT,
            definition_zh        TEXT,
            usage_note_zh        TEXT,
            phrase_type          TEXT NOT NULL,
            source               TEXT NOT NULL,
            source_entry_id      TEXT NOT NULL UNIQUE,
            source_metadata_json TEXT,
            token_count_min      INTEGER NOT NULL,
            token_count_max      INTEGER NOT NULL,
            match_priority       INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE phrase_pattern_token (
            id               INTEGER PRIMARY KEY,
            phrase_id        INTEGER NOT NULL,
            pattern_position INTEGER NOT NULL,
            token_type       TEXT NOT NULL,
            match_type       TEXT,
            match_value      TEXT,
            slot_hint        TEXT,
            min_tokens       INTEGER,
            max_tokens       INTEGER,
            FOREIGN KEY (phrase_id) REFERENCES phrase_entry(id)
        );

        CREATE TABLE phrase_anchor (
            phrase_id     INTEGER NOT NULL,
            anchor_position INTEGER NOT NULL,
            anchor_type   TEXT NOT NULL,
            anchor_value  TEXT NOT NULL,
            PRIMARY KEY (phrase_id, anchor_position),
            FOREIGN KEY (phrase_id) REFERENCES phrase_entry(id)
        );

        CREATE TABLE dictionary_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE UNIQUE INDEX idx_phrase_pattern_position
            ON phrase_pattern_token(phrase_id, pattern_position);
        CREATE INDEX idx_phrase_token_match
            ON phrase_pattern_token(match_type, match_value);
        CREATE INDEX idx_phrase_anchor_lookup
            ON phrase_anchor(anchor_type, anchor_value);
        """
    )


def import_ecdict(connection: sqlite3.Connection, csv_path: Path) -> int:
    insert_sql = """
        INSERT OR IGNORE INTO word_entry (
            word, phonetic, definition_en, translation_zh, pos_profile,
            collins_star, oxford_core, tags, bnc_rank, coca_rank, morphology
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        batch: list[tuple[object, ...]] = []
        for row in reader:
            word = normalized_word(row["word"])
            if not word:
                continue
            batch.append(
                (
                    word,
                    unescape_text(row.get("phonetic")),
                    unescape_text(row.get("definition")),
                    unescape_text(row.get("translation")),
                    unescape_text(row.get("pos")),
                    integer_value(row.get("collins")),
                    boolean_value(row.get("oxford")),
                    unescape_text(row.get("tag")),
                    integer_value(row.get("bnc")),
                    integer_value(row.get("frq")),
                    unescape_text(row.get("exchange")),
                )
            )
            if len(batch) >= 5000:
                connection.executemany(insert_sql, batch)
                batch.clear()
        if batch:
            connection.executemany(insert_sql, batch)
    return connection.execute("SELECT COUNT(*) FROM word_entry").fetchone()[0]


def phrase_tokens(pattern: str) -> list[str]:
    text = pattern.replace("……", "...").replace("…", "...")
    text = re.sub(r"\.\.\.", " ... ", text)
    return text.split()


def slot_for_token(token: str) -> str | None:
    lowered = token.casefold()
    if lowered in {"sb.", "sb", "somebody", "someone"}:
        return "PERSON"
    if lowered in {"sth.", "sth", "something"}:
        return "THING"
    if lowered in {"sb.'s", "sb.s", "somebody's", "someone's"}:
        return "POSSESSIVE"
    if lowered in {"one's", "oneself"}:
        return "POSSESSIVE" if lowered == "one's" else "REFLEXIVE"
    if lowered == "doing":
        return "GERUND"
    return None


def compile_phrase(pattern: str) -> tuple[str, list[dict[str, object]], int, int]:
    raw_tokens = phrase_tokens(pattern)
    if not raw_tokens:
        raise ValueError("empty pattern")

    compiled: list[dict[str, object]] = []
    for index, token in enumerate(raw_tokens):
        if token == "...":
            previous = raw_tokens[index - 1] if index else None
            following = raw_tokens[index + 1] if index + 1 < len(raw_tokens) else None
            if previous and following and slot_for_token(previous) is None and slot_for_token(following) is None:
                if previous.casefold() == "add":
                    token_type, hint = "SLOT", "OBJECT"
                    minimum, maximum = SLOT_RULES[hint]
                else:
                    token_type, hint = "GAP", None
                    minimum, maximum = 1, 3
            else:
                token_type, hint = "SLOT", "GENERIC"
                minimum, maximum = SLOT_RULES[hint]
            compiled.append(
                {
                    "token_type": token_type,
                    "match_type": None,
                    "match_value": None,
                    "slot_hint": hint,
                    "min_tokens": minimum,
                    "max_tokens": maximum,
                }
            )
            continue

        hint = slot_for_token(token)
        if hint:
            minimum, maximum = SLOT_RULES[hint]
            compiled.append(
                {
                    "token_type": "SLOT",
                    "match_type": None,
                    "match_value": None,
                    "slot_hint": hint,
                    "min_tokens": minimum,
                    "max_tokens": maximum,
                }
            )
            continue

        compiled.append(
            {
                "token_type": "LITERAL",
                "match_type": "NORMALIZED",
                "match_value": token.casefold(),
                "slot_hint": None,
                "min_tokens": 1,
                "max_tokens": 1,
            }
        )

    if not any(item["token_type"] == "LITERAL" for item in compiled):
        raise ValueError("pattern has no literal anchor")

    canonical_parts = []
    for item in compiled:
        if item["token_type"] == "LITERAL":
            canonical_parts.append(str(item["match_value"]))
        elif item["token_type"] == "GAP":
            canonical_parts.append("<GAP>")
        else:
            canonical_parts.append(f"<{item['slot_hint']}>")
    minimum = sum(int(item["min_tokens"]) for item in compiled)
    maximum = sum(int(item["max_tokens"]) for item in compiled)
    return " ".join(canonical_parts), compiled, minimum, maximum


def lookup_verb(connection: sqlite3.Connection, token: str) -> bool:
    row = connection.execute(
        "SELECT pos_profile FROM word_entry WHERE word = ? COLLATE NOCASE",
        (token,),
    ).fetchone()
    return bool(row and row[0] and re.search(r"(?:^|/)v(?:[:/]|$)", row[0], re.IGNORECASE))


def classify_phrase(compiled: list[dict[str, object]], connection: sqlite3.Connection) -> str:
    literal_values = [
        str(item["match_value"])
        for item in compiled
        if item["token_type"] == "LITERAL"
    ]
    if any(item["token_type"] in {"GAP", "SLOT"} for item in compiled):
        return "PATTERN"
    if not literal_values:
        return "OTHER"
    first_is_verb = lookup_verb(connection, literal_values[0])
    values = set(literal_values[1:])
    if first_is_verb and values & PARTICLES:
        return "PHRASAL_VERB"
    if first_is_verb and values & PREPOSITIONS:
        return "VERB_PREPOSITION"
    return "FIXED_EXPRESSION"


def make_anchors(compiled: list[dict[str, object]], connection: sqlite3.Connection) -> list[tuple[str, str]]:
    candidates: list[tuple[int, int, str, str]] = []
    for item in compiled:
        if item["token_type"] != "LITERAL":
            continue
        value = str(item["match_value"])
        if not re.search(r"[a-z]", value):
            continue
        row = connection.execute(
            "SELECT bnc_rank, coca_rank FROM word_entry WHERE word = ? COLLATE NOCASE",
            (value,),
        ).fetchone()
        rank = max((row[0] or 0, row[1] or 0)) if row else 0
        content_bonus = 0 if value in FUNCTION_WORDS else 1
        candidates.append((content_bonus, rank, value, str(item["match_type"] or "NORMALIZED")))

    if not candidates:
        raise ValueError("no usable anchor")
    candidates.sort(reverse=True)
    _, _, value, anchor_type = candidates[0]
    return [(anchor_type, value)]


def import_phrases(
    connection: sqlite3.Connection,
    entries_path: Path,
    translations_path: Path,
) -> tuple[int, list[dict[str, str]], dict[str, int], dict[str, int]]:
    translations = {}
    status_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    with translations_path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                row = json.loads(line)
                translations[row["id"]] = row

    entries = []
    with entries_path.open("r", encoding="utf-8") as source:
        entries = [json.loads(line) for line in source if line.strip()]

    insert_phrase = """
        INSERT INTO phrase_entry (
            source_pattern, canonical_pattern, definition_en, definition_zh,
            usage_note_zh, phrase_type, source, source_entry_id,
            source_metadata_json, token_count_min, token_count_max
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    insert_token = """
        INSERT INTO phrase_pattern_token (
            phrase_id, pattern_position, token_type, match_type, match_value,
            slot_hint, min_tokens, max_tokens
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    insert_anchor = """
        INSERT INTO phrase_anchor (
            phrase_id, anchor_position, anchor_type, anchor_value
        ) VALUES (?, ?, ?, ?)
    """

    errors: list[dict[str, str]] = []
    for entry in entries:
        entry_id = entry["id"]
        translation = translations.get(entry_id, {})
        source_pattern = (entry.get("sourceForms") or [entry["canonicalPhrase"]])[0]
        status = translation.get("translationStatus", entry.get("translationStatus", "PENDING"))
        confidence = translation.get("confidence") or ""
        status_counts[status] += 1
        if confidence:
            confidence_counts[confidence] += 1
        try:
            canonical, compiled, minimum, maximum = compile_phrase(entry["canonicalPhrase"])
            phrase_type = classify_phrase(compiled, connection)
            anchors = make_anchors(compiled, connection)
        except ValueError as error:
            errors.append({"source_entry_id": entry_id, "source_pattern": source_pattern, "error": str(error)})
            continue

        cursor = connection.execute(
            insert_phrase,
            (
                source_pattern,
                canonical,
                None,
                translation.get("meaningZh"),
                translation.get("usageNoteZh") or None,
                phrase_type,
                entry["source"],
                entry_id,
                json_text(
                    {
                        "forms": entry.get("sourceForms", []),
                        "lists": entry.get("sourceLists", []),
                        "urls": entry.get("sourceUrls", []),
                    }
                ),
                minimum,
                maximum,
            ),
        )
        phrase_id = cursor.lastrowid
        for position, item in enumerate(compiled):
            connection.execute(
                insert_token,
                (
                    phrase_id,
                    position,
                    item["token_type"],
                    item["match_type"],
                    item["match_value"],
                    item["slot_hint"],
                    item["min_tokens"],
                    item["max_tokens"],
                ),
            )
        for position, (anchor_type, anchor_value) in enumerate(anchors):
            connection.execute(
                insert_anchor,
                (phrase_id, position, anchor_type, anchor_value),
            )

    return (
        connection.execute("SELECT COUNT(*) FROM phrase_entry").fetchone()[0],
        errors,
        dict(status_counts),
        dict(confidence_counts),
    )


def write_meta(
    connection: sqlite3.Connection,
    ecdict_commit: str,
    secondla_commit: str,
    dictionary_count: int,
    phrase_count: int,
) -> None:
    values = {
        "package.version": "0.1.0",
        "schema.version": "1",
        "build.time": datetime.now(timezone.utc).isoformat(),
        "ecdict.commit": ecdict_commit,
        "ecdict.license": "MIT",
        "ecdict.entry_count": str(dictionary_count),
        "2ndla.commit": secondla_commit,
        "2ndla.license": "CC BY-SA 4.0",
        "2ndla.entry_count": str(phrase_count),
        "pattern.compiler.version": "1",
        "lemma.rules.version": "1",
    }
    connection.executemany(
        "INSERT INTO dictionary_meta(key, value) VALUES (?, ?)",
        values.items(),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ecdict-csv", type=Path, required=True)
    parser.add_argument("--secondla-entries", type=Path, default=Path("sources/2ndla/entries.jsonl"))
    parser.add_argument("--secondla-translations", type=Path, default=Path("translations/2ndla/translation-full-output.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("release/lyric-dictionary.sqlite"))
    parser.add_argument("--manifest", type=Path, default=Path("release/manifest.json"))
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--ecdict-commit", default="bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b")
    parser.add_argument("--secondla-commit", default="4362d151decd8fd92e511bdd2cda31efbe63c8eb")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()

    connection = sqlite3.connect(temporary)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=MEMORY")
    create_schema(connection)
    dictionary_count = import_ecdict(connection, args.ecdict_csv)
    phrase_count, errors, status_counts, confidence_counts = import_phrases(
        connection, args.secondla_entries, args.secondla_translations
    )
    args.build_dir.mkdir(parents=True, exist_ok=True)
    error_path = args.build_dir / "build-errors.jsonl"
    error_path.write_text(
        "".join(json_text(error) + "\n" for error in errors),
        encoding="utf-8",
    )
    if errors:
        connection.close()
        temporary.unlink()
        raise SystemExit(f"build failed: {len(errors)} phrase compilation errors; see {error_path}")

    write_meta(connection, args.ecdict_commit, args.secondla_commit, dictionary_count, phrase_count)
    connection.commit()
    connection.execute("VACUUM")
    connection.close()
    temporary.replace(args.output)

    check_connection = sqlite3.connect(args.output)
    token_count = check_connection.execute("SELECT COUNT(*) FROM phrase_pattern_token").fetchone()[0]
    anchor_count = check_connection.execute("SELECT COUNT(*) FROM phrase_anchor").fetchone()[0]
    meta_count = check_connection.execute("SELECT COUNT(*) FROM dictionary_meta").fetchone()[0]
    check_connection.close()

    summary = {
        "database": args.output.name,
        "dictionary_entries": dictionary_count,
        "phrase_entries": phrase_count,
        "pattern_tokens": token_count,
        "anchors": anchor_count,
        "translation_status_counts": status_counts,
        "confidence_counts": confidence_counts,
        "compilation_errors": len(errors),
    }
    (args.build_dir / "build-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.build_dir / "build-report.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "ecdict_commit": args.ecdict_commit,
                "secondla_commit": args.secondla_commit,
                "schema_version": 1,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "releaseVersion": "0.1.0",
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "artifact": args.output.name,
        "sha256": sha256(args.output),
        "sources": [
            {
                "name": "ECDICT",
                "role": "word_dictionary",
                "commit": args.ecdict_commit,
                "license": "MIT",
                "url": "https://github.com/skywind3000/ECDICT",
            },
            {
                "name": "2ndLA/english-phrases",
                "role": "phrase_dictionary",
                "commit": args.secondla_commit,
                "license": "CC BY-SA 4.0",
                "url": "https://github.com/2ndLA/english-phrases",
            },
        ],
        "tables": {
            "word_entry": dictionary_count,
            "phrase_entry": phrase_count,
            "phrase_pattern_token": token_count,
            "phrase_anchor": anchor_count,
            "dictionary_meta": meta_count,
        },
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["tables"], ensure_ascii=False))
    print(f"output={args.output}")
    print(f"sha256={manifest['sha256']}")


if __name__ == "__main__":
    main()
