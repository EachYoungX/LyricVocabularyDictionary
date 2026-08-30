# GPT-5.6 Luna high-reasoning pilot

Use GPT-5.6 Luna with **High** reasoning and
`translation-pilot-high-input.jsonl` as the input. Save the result as
`translation-pilot-high-output.jsonl`. This is a second, independent
300-entry sample for measuring quality and five-hour Codex allowance
consumption.

Return one JSON object per input line, preserving `id` and `canonicalPhrase`
exactly:

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

Quality rules:

- Translate the complete phrase, never by concatenating ECDICT word entries.
- Distinguish an established idiom or phrasal verb from a literal
  collocation.
- Keep the established Chinese meaning concise and natural.
- Use `REVIEW_REQUIRED` with an empty `meaningZh` for malformed, ambiguous,
  or unstable candidates rather than inventing a meaning.
- Preserve exactly one output object per input line and add no extra fields.

After the run, record the Codex five-hour allowance before and after the task,
the number of valid output lines, and a manual spot-check result. The output
must remain a pilot artifact until those checks pass.
