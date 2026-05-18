---
name: kephalaia-editorial-fingerprint-mapping
description: "Manual workflow for mapping German editorial sentences to cluster-array fingerprints in temp/editorial_sentences.json. Use when: Kephalaia editorial fingerprints, German notes, LLM witness lines, Manual Reviewer editorial layer, cluster arrays, abgerieben, zerstört, leer, unlesbar, geringe Spuren."
---

# Kephalaia Editorial Fingerprint Mapping

## When To Use

Use this skill when mapping German editorial notes from the Kephalaia LLM witness transcriptions into `temp/editorial_sentences.json`, or when working on the Manual Reviewer editorial layer that overlays those notes.

This is a manual inspection workflow. Do not replace it with a clever alignment script, statistical guess, line-index shortcut, or broad extraction pass.

## Core Rule

The only assumption allowed is this:

> If a German editorial sentence appears on a line in the LLM witness, the app data line we use should say almost the same thing in its actual content.

That content match controls everything. Line indexes can help you look nearby, but they are never evidence by themselves. The app-data line must be identified by comparing the witness line's real text and surrounding context against the app data's real token labels.

## Target Output

`temp/editorial_sentences.json` maps each full German editorial sentence to one or more cluster arrays:

```json
{
  "Rest abgerieben": [
    [236, 155, 220, 50, 217, 219, 14, 26, 87, 65, 26, 219, 155, 236]
  ],
  "verwischt und abgerieben": []
}
```

One array is one fingerprint. It is the ordered list of cluster IDs for the full sentence, not for individual words.

## Character Count Rule

For a candidate occurrence, the fingerprint length must equal the number of characters in the full German sentence after removing spaces.

Examples:

| Sentence | Required Cluster Count |
|---|---:|
| `leer` | 4 |
| `abgerieben` | 10 |
| `zerstört` | 8 |
| `geringe Spuren` | 13 |
| `Rest abgerieben` | 14 |
| `verwischt und abgerieben` | 22 |

Do not silently drop punctuation. For phrases with punctuation such as `unlesbar (abgerieben)`, count the sentence without spaces as written unless the user has explicitly defined a different rule. If the app data does not provide positions for punctuation, leave the phrase empty or ask before changing the rule.

## Sources

Use these sources for each candidate:

| Source | Path | Role |
|---|---|---|
| LLM witness transcription | `output/projects/kephalaia_v2/coptic/transcriptions/keph_pNNN_pass2.txt` | Finds German editorial sentence occurrences and their actual line context |
| App baseline data | `manual_reviewer/data/ingest/initial_baseline/pNNN.json` | Supplies token labels and cluster IDs used by the Manual Reviewer |
| Browser reviewer | `http://localhost:3002/review/NNN` | Optional visual aid for ambiguous line context |
| Current mapping file | `temp/editorial_sentences.json` | The file to update, preserving existing verified arrays |

`output/**` is commonly ignored by search settings. When using workspace search, include ignored files.

## Required Workflow

### 1. Read The Current Mapping First

Before editing, inspect `temp/editorial_sentences.json`. The user or another tool may have changed it. Preserve existing verified arrays unless the user explicitly tells you to remove or reset them.

### 2. Work One Sentence At A Time

Pick one key from `temp/editorial_sentences.json`. Do not bulk-fill multiple keys from a script. Do not infer a family of mappings from one phrase and apply it to another.

### 3. Find Witness Occurrences

Search the LLM witness transcription files for the exact German sentence.

Read the surrounding lines in the witness file. The important thing is the complete line content, including:

- Coptic before the German sentence
- Coptic after the German sentence
- Lacuna dots or brackets around the sentence
- Whether the German sentence is standalone, leading, trailing, or mid-line

### 4. Find The App Data Line By Content

Open the corresponding app baseline page JSON and inspect the line labels.

The line is acceptable only when the app-data line says almost the same thing as the witness line. Compare actual text, not line numbers:

- If the witness has Coptic before the German phrase, the app line should have matching Coptic before the editorial token run.
- If the witness has Coptic after the German phrase, the app line should have matching Coptic after the editorial token run.
- If the witness line is standalone, the app line should be a standalone editorial-like row, not a nearby Coptic row chosen by index.
- If the app line content does not match the witness line, reject the occurrence.

Line indexes may help you find candidate rows faster, but they do not decide the mapping. Never write an array because `line_index`, `v1_line_index`, or the printed witness line number appears to line up.

### 5. Inspect Tokens In Order

For the content-matched app line, inspect each token in order with at least:

- ordinal position in row
- `cluster`
- `label`
- `review_sheet_raw_label`

Use geometry only when needed to resolve a boundary. The fingerprint itself is clusters only.

### 6. Isolate The Full Editorial Sentence

The editorial run is the contiguous token run corresponding to the full German sentence.

Bound it by the content match:

- Use the Coptic before the phrase to identify where the editorial run starts.
- Use the Coptic after the phrase to identify where the editorial run ends.
- For standalone lines, the whole row must have exactly the required number of positions, or the extra positions must be explainable from visible non-sentence content. If not, reject it.

Do not slice off extra tokens just because the desired phrase length says so. If a content-matched row has 33 positions for a 22-character sentence and no reliable boundary explaining which 11 are outside the sentence, leave the key empty for that occurrence.

### 7. Enforce The Length Exactly

Before accepting, count the cluster IDs. The count must equal the sentence length after removing spaces.

Reject the occurrence when:

- The token run is shorter than the sentence length.
- The token run is longer and the extra positions cannot be explained by matching surrounding content.
- The row is content-mismatched.
- The row was found only because of an index.
- The phrase was split into word-level fingerprints.

### 8. Add Only Verified Arrays

Update only the key you are working on. Preserve all other keys and arrays.

Use `apply_patch` for the edit. Do not rewrite the file wholesale unless the user explicitly asks for a reset.

If there are no acceptable occurrences, leave the key as `[]`.

## Explicit Prohibitions

- Do not use line indexes as authority.
- Do not assume the pass2 printed line number maps to any particular app row.
- Do not run bulk mapping scripts to generate fingerprints.
- Do not infer fingerprints from cluster frequency alone.
- Do not accept a row because it contains many `E` labels.
- Do not turn German editorial notes into fake Coptic.
- Do not create phrase overlays in the token strip.
- Do not build fingerprints per word. The unit is the full sentence.
- Do not pad or truncate arrays to make them fit.
- Do not remove existing verified arrays unless explicitly requested.

## Acceptance Examples

### Acceptable

Witness line:

```text
6 ⲛⲉϥ ⲍⲓ ⲡⲣⲟⲁⲟⲧⲏⲥ ⲍⲓ ⲣⲉϩⲍⲱⲧⲃⲉ Rest abgerieben [ⲥⲥⲏⲍ ⲉⲧⲃⲉ]
```

App data line visibly contains the same Coptic before the note and the same bracketed Coptic after it. The token run between those anchors has exactly 14 positions, matching `Rest abgerieben` without spaces. Accept the 14 clusters.

### Not Acceptable

Witness line:

```text
16 verwischt und abgerieben ⲉⲕⲕⲗⲏⲥⲓⲁ ⲉⲧⲥⲁⲟⲩⲛⲉ[ⲙ?]
```

If the matching app row has 33 ambiguous positions before the Coptic while the phrase requires 22, and there is no content boundary proving which 22 positions are the sentence, do not choose a slice. Leave that occurrence unused.

## Reporting While Working

After each sentence, report briefly:

- which witness occurrences were inspected
- which app-data line(s) content-matched
- which arrays were accepted, or why the key remains empty

Keep the report factual. Do not justify rejected rows with cleverness; the reason should be visible from content mismatch, non-exact length, or unresolved boundary.