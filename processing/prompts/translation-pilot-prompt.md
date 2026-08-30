# Translation pilot

Use GPT-5.6 Luna in Codex with `translation-pilot-input.jsonl` as the input.
Translate the complete phrase as an English phrase. Do not translate by
looking up or concatenating the individual words in ECDICT.

Return one JSON object per input line, preserving the input `id` and
`canonicalPhrase` exactly:

```json
{
  "id": "2ndla:look forward to",
  "canonicalPhrase": "look forward to",
  "meaningZh": "期待；盼望",
  "usageNoteZh": "后接名词或动名词",
  "translationStatus": "GENERATED",
  "confidence": "HIGH"
}
```

Rules:

- Provide a concise Chinese meaning for the complete phrase.
- Prefer the established idiomatic meaning; mention a literal meaning only
  when it is commonly used and materially different.
- Do not invent an idiomatic meaning for a literal collocation.
- Keep `meaningZh` empty and set `translationStatus` to `REVIEW_REQUIRED` when
  the source phrase is malformed, ambiguous, or not a stable expression.
- Do not add examples or fields outside the schema.

The pilot is for quality and quota measurement. It must not be merged into
the formal phrase dictionary until JSON validity, phrase preservation, and
human spot checks pass.
