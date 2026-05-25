---
name: coptic-ocr-reviewer
description: "Use when: reviewing unreviewed Coptic OCR scan-page markdown exports from the printed Kephalaia paper/edition, inspecting Final Reviewer Output text for suspicious OCR inconsistencies, and applying patterns learned only from manually corrected pages p010-p029 in temp/manual_reviewer_markdown_export/out."
---

# Coptic OCR Reviewer Skill

Use this skill to review unreviewed scan-page OCR markdown exports from the printed Kephalaia paper/edition:

`temp/manual_reviewer_markdown_export/out`

The skill is trained only on the manually reviewed pages `p010.md` through `p029.md`. Do not mine examples or rules from any other repository files. General Coptic reading competence may be used as language intuition, but no other repo content, dictionaries, scripts, OCR artifacts, notes, or source files should be consulted for the review.

## Source Model

These exports are not OCR of the original manuscript. They are OCR of a scanned printed/scholarly page analyzing/transcribing the Kephalaia of the Teacher.

- Treat printed Coptic letters, supralinear marks, diaereses, underdots, brackets, lacuna dots, and German status notes as part of the printed transcription system when they are intentionally printed.
- Treat stray specks, smudges, isolated dots, and visual noise as likely scan/print/OCR artifacts unless the printed-page pattern clearly supports them as transcription marks.
- German status notes such as `abgerieben` or `zerstort` describe the editor's assessment of the underlying source, but the OCR review only judges the printed/scanned page export.
- Do not infer physical manuscript damage from the scan itself. Use "damaged" only when referring to the printed transcription's own bracket/dot/status-note conventions.

## Scope Discipline

- Use only the page markdown export being reviewed, plus the correction patterns recorded here from `p010.md`-`p029.md`.
- Do not use `p030.md` as training evidence.
- Do not use later unreviewed pages as evidence for general rules.
- Treat `Reviewed: yes` pages as ground truth only inside the training boundary.
- Treat `Reviewed: no` pages as candidate OCR text, even when the section is named `Final Reviewer Output`.
- Do not rewrite uncertain readings just to make them look clean. The reviewed pages preserve uncertainty, brackets, lacuna dots, `?`, and `E` where the uncertainty is still real.

## Page Structure

Each page markdown normally contains:

- metadata such as `Lines`, `Reviewed`, `Done lines`, `Special lines`, and `Flagged lines`
- `## Final Reviewer Output`
- `## Pre-Manual-Correction Output`
- `## Final Reviewer X-Center Details`
- `## Pre-Manual-Correction X-Center Details`

For unreviewed pages, start by reading the metadata and the `Final Reviewer Output`. Use the pre-manual block only as secondary evidence if the page contains both blocks and a comparison helps explain a suspicion. A text-only review must not depend on page images/scans.

## Review Output Format

Report findings line by line. Do not silently edit the page unless the user explicitly asks for corrections to be applied.

Use this format:

```markdown
Page pNNN.md

- LXX: suspicious reading
  Observed: `...`
  Proposed: `...`
  Confidence: high | medium | low
  Reason: concise explanation grounded in training patterns and/or Coptic continuity.
```

If a page has no strong textual inconsistencies, say so and list any low-confidence residual concerns separately.

## What The Training Set Shows

Across `p010.md`-`p029.md`, 138 of 672 final lines differ from pre-manual OCR. Most changes are small, not wholesale rewrites. The reviewer should therefore prefer targeted correction proposals over broad reconstruction.

Common correction types:

- Raw dot punctuation inside words often becomes an underdot on the neighboring letter.
- Missing diaeresis on `ⲓ` is common, especially in `ⲁⲓ̈`, `ⲁϩⲣⲏⲓ̈`, `ⲟⲩⲁⲓ̈`, and `ⲡϫⲁ̣ⲓ̈`.
- Whole-line OCR noise made from `E`, `?`, stray brackets, and a few Coptic letters often becomes a German status note.
- Left-margin starts are fragile. The reviewer often inserted missing initial letters or corrected opening brackets.
- Supralinear abbreviations and overlines are load-bearing and should be preserved exactly.
- Coptic-looking words were corrected by local language continuity, but lacuna brackets and dots were retained where the text was not recoverable.

## High-Value OCR Warning Signs

Flag a line when it contains these patterns and the surrounding line is otherwise Coptic:

- Dense ASCII noise: `E`, `EE`, `EEE`, `?`, `??`, `?EEE`, `?EE?`, or mixed clusters like `E??E`.
- Bracket noise at the beginning or end: `[[[`, `][`, `]]`, or a dangling `]` where a restoration bracket or German status note is more likely.
- Dot-separated Coptic inside an otherwise continuous word: `ⲁ.ⲃⲁ.ⲗ`, `ⲡⲥ.ⲁ.ⲡ`, `ⲧ.ⲟⲛ.ⲉ`, `ⲡϫ.ⲁⲓ`, `ⲅ.ⲣⲁ`, `ⲡ.ⲣ̣ⲱⲙⲉ`.
- Question marks embedded where the target word is otherwise clear: `ⲥⲁⲣ?`, `ⲥⲕⲁⲛ?ⲓⲍⲉ`, `ⲛ̄ⲧ.ϣⲏ̣ⲣ`.
- A single isolated Coptic letter on a line where the surrounding page likely continues a printed damaged-text note, heading, or section.
- A left-edge missing prefix in a line that otherwise begins mid-word.

Do not automatically delete all `E`, `?`, or dots. The reviewed pages retain them when they remain unresolved.

## Dot And Underdot Behavior

The most frequent short replacement in the training set was raw `.` becoming combining underdot `̣`. Use this only when the dot is adjacent to a letter and the result produces a plausible word or damaged-letter reading.

Observed examples:

- `ⲁ.ⲃⲁ.ⲗ` or `ⲁⲃ.ⲁ.ⲗ` can become `ⲁⲃ̣ⲁⲗ̣` or `ⲁⲃⲁ̣ⲗ̣` depending on the letter positions.
- `ⲡⲥ.ⲁ.ⲡ` became `ⲡⲥⲁ̣ⲡ̣`.
- `ⲧ.ⲟⲛ.ⲉ` became `ⲧⲟ̣ⲛ̣ⲉ`.
- `ⲡϫ.ⲁⲓ` became `ⲡϫⲁ̣ⲓ̈`.
- `ⲅ.ⲣⲁⲫⲁⲩ̣ⲉ` became `ⲅ̣ⲣⲁⲫⲁⲩ̣ⲉ`.
- `ⲛ̄ⲧ̣.ϣⲏ̣ⲣ` became `ⲛ̄ⲧ̣ϣ̣ⲏ̣ⲣ`.

Keep true lacuna dots as dots, especially long runs such as `........` and dots inside brackets.

## Diaeresis On Iota

The training set repeatedly adds diaeresis to iota in words where the OCR saw plain `ⲓ`.

Common checked forms:

- `ⲁⲓ̈`
- `ⲁϩⲣⲏⲓ̈`
- `ⲟⲩⲁⲓ̈`
- `ⲡϫⲁ̣ⲓ̈`
- `ⲡⲉⲓ̈`
- `ⲉⲓ̈`
- `ⲃⲉⲗⲓ̈ⲁⲣ`

Flag missing diaeresis when the surrounding form strongly matches one of these. Do not add diaeresis to every iota.

## Supralinear And Abbreviated Forms

These marks are not decoration. Preserve and flag damaged forms when OCR drops or corrupts the mark structure.

Observed recurring forms include:

- `ⲙ︤ⲛ︥`
- `ϩ︤ⲛ︥`
- `ⲛ︤ϥ︥`
- `ⲓ︤ⲏ︦ⲥ︥`
- `ⲛⲓ︤ⲏ︦ⲥ︥`
- `ⲡⲭ︤ⲣ︦ⲥ︥`
- `ⲡ︤ⲛ︦ⲁ︥`
- `ⲡ︤ⲛ︦ⲓ︦ⲕ︥`
- `ⲡⲡⲣ︤ⲕ︦ⲗ︦ⲥ︥`

Common review action: preserve the abbreviation, repair the surrounding Coptic, and avoid expanding it unless the page already uses an expanded bracketed restoration.

## German Status Notes

The reviewed pages use compact German status notes for text the printed edition labels as damaged, unreadable, rubbed, blank, or partly visible. These notes are intentional reviewer statuses, not Coptic text.

The Coptic OCR engine does not reliably recognize Latin characters. Raw OCR strings that look partly Latin or German are therefore not trustworthy spellings. Treat them as noisy evidence that a German status note may be needed, not as exact text to preserve. Use the corrected reviewed-note patterns below as the guide.

Established note vocabulary from the training pages:

- `nichtgelesen`
- `leer`
- `abgerieben`
- `Restabgerieben`
- `geringeSpuren`
- `ganzgeringeSpuren`
- `unlesbar`
- `zerstort`
- `fastvolligzerstort`
- `fastganzzerstort`
- `zerstortundabgerieben`
- `verwischt`
- `verwischtundabgerieben`
- `einstweilenunlesbar`

Variant note-like strings also occur in the corrected pages, including `}.Sgeringepuren`, `}beinstweilenunlesar`, and `}kstarabgerieben`. Treat these as evidence that Latin status-note regions can be noisy at printed margins because the Coptic OCR is not reading Latin properly. When reviewing an unreviewed page, flag such variants as possible German status-note lines rather than confidently normalizing them.

Strong German-status-note candidates:

- A whole line or line segment is mostly `E`, `?`, brackets, and a few Coptic letters.
- The line appears in a printed damage/status-note band where adjacent lines have long dot runs.
- OCR gives sequences like `[[[E???E?EⲟE?`, `][?.ⲟⲓ.ⲥ̈?]???EEⲟⲓE]]`, or `[EE?ⲟⲧⲥ̈ⲓⲧ??ⲟⲥ??E??E?E??`.

Training examples:

- `[[[E???E?EⲟE?` -> `nichtgelesen`
- `][?.ⲟⲓ.ⲥ̈?]???EEⲟⲓE]]` -> `}fastvolligzerstort`
- `[EE?ⲟⲧⲥ̈ⲓⲧ??ⲟⲥ??E??E?E??...............` -> `zerstortundabgerieben...............`
- `[ⲥ??EE?E?EE` -> `}abgerieben`
- `][E??ⲟⲓ?E??E?E??Eⲟ?ⲥE]]` -> `}einstweilenunlesbar`
- `Eⲓⲥ???E?EⲟEE` -> `nichtgelesen`

## Brackets, Braces, And Parentheses

Square brackets mark restorations or damaged/lost text and must be preserved when they are meaningful. The reviewed pages also use `}` at the start of some damage-note lines.

Review rules:

- A dangling `]` at the beginning of a Coptic line is suspicious; it may need `[` or may be part of a German-status-note conversion.
- Do not remove bracketed restorations merely because a word would be smoother without them.
- Empty `[]` segments occur in corrected pages and should not be rejected automatically.
- Parentheses can be corrected inside bracketed restorations when the OCR mangles them.

Observed examples:

- `]ⲕⲁⲣ]ⲡⲟ...` -> `[ⲕⲁⲣ]ⲡⲟ...`
- `ⲧϣ... [ϥⲁⲧ[ⲣ)ⲉϥϩⲉⲣ]` -> `...[ϥⲁⲧ(ⲣ)ⲉϥϩⲉⲣ]`
- `ⲙ̣...ⲡⲉⲧ[ⲓⲛ)ⲁ]` -> `...ⲡⲉⲧ[(ⲛ)ⲁ]`

## Recurrent Coptic Continuity Checks

Use these as local plausibility anchors. Flag only when the surrounding string strongly supports the form.

Common recurring forms in the training pages:

- `ⲉⲕⲕⲗⲏⲥⲓⲁ`
- `ⲡⲕⲟⲥⲙⲟⲥ`
- `ⲁⲡⲟⲥⲧⲟⲗⲟⲥ`
- `ⲕⲁⲣⲡⲟⲥ`
- `ⲡⲥⲧⲩⲗⲟⲥ`
- `ⲡϣⲏⲛ`
- `ⲡⲁⲣⲙⲟⲩⲧⲉ`
- `ⲁⲃⲁⲗ`
- `ⲁϩⲣⲏⲓ̈`
- `ⲙⲙⲁϥ`
- `ⲛ̄ⲥⲱⲥ`
- `ⲡϫⲁ̣ⲓ̈`
- `ⲥⲁⲣⲝ`
- `ⲥⲕⲁⲛⲓⲍⲉ`
- `ⲇⲟⲅ̣ⲙ̣ⲁ̣`

Observed corrections:

- `ⲡ̣ⲁⲣⲛⲧⲟⲩⲧⲉ` -> `ⲡ̣ⲁⲣⲙⲟⲩⲧⲉ`
- `ⲥⲕⲁⲛ?ⲓⲍⲉ` -> `ⲥⲕⲁⲛⲓⲍⲉ`
- `ⲥⲁⲣ?` -> `ⲥⲁⲣⲝ`
- `ⲧⲏⲣⲟⲩ̣?EEE` may keep `?EEE` if unresolved but can still take a local correction before it.
- `ⲇⲟⲅⲙⲁ` sometimes receives underdots as `ⲇⲟⲅ̣ⲙ̣ⲁ̣`.

## Left And Right Margin Corrections

Margins are the most unstable zone. The training pages often add, remove, or repair one to three characters at the start or end of a line.

Common additions or repairs:

- missing initial `ⲧ`, `ⲙ`, `ⲡ`, `ϣ̣`, `ⲁⲝ`, `ϫⲙ`, `ⲧⲯⲩ`
- initial `?` removed when the following Coptic line is otherwise clear
- initial `]` corrected to `[` or converted to `}` before a damage note
- final stray `?]` removed when it is not part of a readable restoration

Examples:

- initial `ϥ...` -> `ⲧϥ...`
- initial `ⲧⲁϩ...` -> `ⲙ̄ⲙⲧⲁϩ...`
- initial `ϣⲁⲣⲡ...` -> `ⲡϣⲁⲣⲡ...`
- `?ⲉⲧⲃⲉ... ?` -> `ⲉⲧⲃⲉ...`
- `]ⲉⲓ̈ⲡ̣ⲉ...` -> `[ⲡ]ⲉⲓ̈ⲡ̣ⲉ...`

These are usually medium-confidence unless the surrounding Coptic is very clear.

## Confidence Rules

High confidence:

- A raw noisy line matches the established damage-note pattern and contains little recoverable Coptic.
- A repeated form is obvious, such as `ⲥⲁⲣ?` -> `ⲥⲁⲣⲝ`, `ⲁϩⲣⲏⲓ` -> `ⲁϩⲣⲏⲓ̈`, or a dot-separated word matching a repeated token.
- A supralinear abbreviation is visibly present but one mark/letter is missing.

Medium confidence:

- A left-margin letter appears missing but the line can still be read without it.
- Dot-to-underdot repair improves a plausible word but is not forced by a repeated phrase.
- A bracket orientation looks wrong but the line still has mixed damage.

Low confidence:

- The line is heavily damaged and several reconstructions are possible.
- The candidate correction depends mainly on a semantic guess.
- The change would remove uncertainty marks that the reviewed pages commonly preserve.

## What Not To Do

- Do not use other repo files to validate vocabulary or readings.
- Do not normalize all damage notes to standard German spelling.
- Do not replace every dot with an underdot.
- Do not remove all `E`, `?`, or bracket clutter automatically.
- Do not expand supralinear abbreviations.
- Do not turn bracketed restorations into unbracketed text unless the reviewed-page pattern clearly supports it.
- Do not treat a clean-looking Coptic line as wrong just because it differs from pre-manual OCR.

## Final Review Checklist

Before returning a review:

- Confirm the target page path and `Reviewed` metadata.
- State that the review used only the page export and this `p010`-`p029` pattern skill.
- List line-level findings with confidence.
- Separate likely corrections from low-confidence questions.
- Preserve uncertainty when the evidence is not strong.
