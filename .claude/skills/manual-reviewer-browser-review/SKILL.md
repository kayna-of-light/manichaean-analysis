---
name: manual-reviewer-browser-review
description: "Use when: visually inspecting a Kephalaia printed scan in the Manual Reviewer browser app, correcting character labels, overlines, dots, brackets, bounding boxes, or line assignments through browser controls. Documents assisted repair procedures, persistence checks, and known limitations; not a validated autonomous Coptic proofreading skill."
---

# Manual Reviewer — Browser-Assisted Visual Repair

## Scope and capability boundary

Use for the open Manual Reviewer page when the user authorizes visual inspection or correction through the browser. This is distinct from the text-only `coptic-ocr-reviewer` skill, whose linguistic evidence remains restricted to reviewed exports p010–p029.

**Tool operation is not proof of reliable visual proofreading.** The page-190 trial produced saved local repairs, but a user-identified error on displayed line 15 was initially missed even after magnification and checking neighbouring numbering. Only after the user directed attention to the warning signals did targeted inspection identify a printed underdot on sha that was absent from its saved label. The finding was identified, not corrected during that inspection. This recovery required user guidance; do not claim this workflow can independently certify every character, mark, or line.

- Successful local corrections demonstrate those particular actions, not complete page accuracy.
- If an error cannot be identified, say so. Do not invent a correction, a diagnosis, or a retrospective explanation of why it was missed.
- A user saying a feature was missed is evidence that the review was incomplete. Do not recast this as uncertainty about whether an error exists.
- When the user rejects further autonomous review, stop page edits. Documentation and display cleanup may continue.
- A saved change and a reloaded change are not necessarily a correct reading. Persistence and visual correctness must be reported separately.

## Source model and evidence

The immediate source is a **scan of a printed scholarly edition**, not a photograph of the original manuscript. Preserve its Coptic typography and editorial notation. Underdots, brackets, lacuna dots and German status notes can intentionally describe uncertainty or loss in the underlying manuscript; they are not automatically scan damage.

Use the displayed scan for the reading; use the DOM for element identity, coordinates, labels and controls. A linguistically plausible form does not demonstrate that a printed mark is present or absent. Do not consult translations or other pages to supply missing readings unless authorized.

Keep these checks separate:

1. **Letter identity:** does the label match the printed letter?
2. **Marks:** inspect above and below each relevant letter independently of word recognition. Distinguish overline, single above-dot, diaeresis, underdot, baseline punctuation and lacuna dot.
3. **Ownership:** does a letter or mark belong to this row, or to its neighbour? Inspect neighbouring print before deciding.
4. **Box geometry:** does the box select the intended glyph rather than half of it, another glyph, or empty space?
5. **Image strip:** does the displayed crop include or clip adjacent text? This is separate from saved token assignment.

Existing overline groups can encode a shared bar separately from the base-letter box. Check both label/group data and the print before treating a box that excludes the bar as an error. Never infer that every body box must span every diacritic.

## Browser workflow

Read [Browser tool recipes and observed pitfalls](./references/browser-tools.md) for actionable examples. Use currently available browser tools; load deferred tools first where required by the environment.

### 1. Establish the current state

- Reuse the shared review tab; confirm its URL and page number. Do not navigate the user's review tab away from unsaved work.
- Read the browser accessibility state before interacting. Scope later reads to a line card or dialog to avoid the very large full-page snapshot.
- Record the displayed row number, current labels and relevant boxes before editing. Do not reset prior user corrections.
- The displayed row number, array position and internal line index are **not interchangeable**. On page 190, displayed line 11 appeared as internal line 12 in the character chooser. Duplicated rows have labels such as 10.01. Never silently reinterpret a user's line number.
- Retrieve the scan URL from the actual SVG `<image>` element. Use a separate image tab if helpful; reuse an existing one.

### 2. Triage warnings, then inspect at a usable scale

- **Read the warning signals before targeted magnification.** Inventory coloured dots beneath labels and geometry warnings; retrieve their actual reasons rather than only noting their colour. The small coloured dots may have no title or accessible label, so an accessibility snapshot or tooltip query can miss them entirely.
- Associate each warning with its exact token and confirmed internal line index. The warning endpoint uses internal indices, not necessarily the user's displayed row number. The browser reference explains how to read it without changing data.
- Let a specific warning select the visual question: a diacritic-variant warning calls for checking the mark; a possible missing successor calls for inspecting the right margin and continuation. Frequency is a lead, never permission to change the print. Also inspect unwarned characters: absence of a warning does not establish correctness.
- On page 190, displayed line 15, sha (blob 20, internal line 16) warned that `ϣ̣` was more common than `ϣ` (2.0×). The enlarged scan then showed the separate dot below sha's bowl, inside its descending tail. The final eta (blob 40) separately warned about a rare line ending; that statistic alone did not establish a missing successor.
- Inspect the whole line, both margins, and enough of adjacent rows to assign dots/overlines correctly.
- Enlarge suspicious regions, not merely the full browser window. The small chooser preview may omit the very mark under investigation; use its zoom-out control to include context.
- Screenshots supply visual evidence, not stable click coordinates. Locate controls and geometry in the DOM before acting.
- Native image tabs may automatically reset styling/zoom. A temporary magnified SVG crop in the review tab is a display-only alternative; never mistake it for saved data. Remove it before clicks, after inspection, and at the end of the task.
- Do not read a plausible word and assume its marks are correct. Check letter sequence, above-marks, below-marks and brackets separately. This procedure is a checklist, not a guarantee of detection.

### 3. Apply the smallest verified repair

**Open controls:** Hover the `.line-card` to reveal its toolbar. Sidebar line buttons select/scroll; they do not open the line editor. Use the explicit `Open line editor for line …` button. Clicking a token label or polygon opens the character chooser.

**Relabel a token:** Use the Coptic palette or supported key presses. The character chooser textbox is a read-only proxy: Playwright `fill()` can change its visible DOM value but not application state, so Save can preserve the old label. For Latin notes, enable **ABC** literal mode, press the desired key, and save. Check the actual saved token label afterwards. Do not apply this textbox rule indiscriminately to the separate line editor or sequence input.

**Move a token:** Use `Move to line above/below` only after establishing its correct physical row. After each move reacquire source and destination cards and confirm that the token exists exactly once on the correct row with unchanged geometry. Avoid repeated clicks on stale state. Do not use deletion as a substitute for moving a genuine letter.

**Add a missing box:** Hover the target row and use `Add bbox`. Draw in source-image coordinates transformed through the live SVG to screen coordinates. The toolbar disappears in drawing mode, so a locator defined by a toolbar descendant stops matching; retain a verified card index during this operation and assert its displayed number. Label the new box in the chooser and save. Exit drawing mode with Escape before continuing elsewhere.

**Resize a box:** The line editor shows active base-token polygons as read-only overlays. Saved/new boxes have movable rectangles and corner handles. Select the correct rectangle, read its resize handles, and drag using the SVG transform. `Accept` persists line-editor changes; `Cancel` does not. Do not Generate and overwrite a whole line just to fix one box. If a base box requires replacement, preserve its label/marks and replace only that token, verifying that no duplicate remains.

**Remove a false token:** Establish what the print actually contains. In the heading trial, three question-mark tokens were separately recognized bars already represented as overlines on their owning letters. Removing those duplicate tokens did not mean deleting the printed bars. Confirm mark ownership first; do not delete uncertain ink to make the text cleaner.

**Create a missing row:** `Duplicate row` copies all active boxes; it is not a blank-row command. Before duplicating, ensure that separate row ownership is actually needed. In the duplicate's line editor, remove unwanted copied boxes, retaining only the intended content. Accept and verify the new row before removing corresponding source tokens. Never reset the source row. Verify each glyph exists once in the final result. This does not fix the duplicated image strip's crop bounds.

### 4. Verify before claiming success

- Re-read the saved labels and geometry after each coherent edit. Wait for a specific UI state, not an arbitrary sleep. A timeout is not evidence that an edit failed; inspect state before retrying.
- Finish pending line-editor work before reload. Reload the review page and confirm the corrected labels, row membership, box coordinates and mark groups persist.
- Recompare the result with the print. Preserve prior user corrections and intentionally printed uncertainty.
- Do not use colour warnings as ground truth. Large decorative `pi` initials on page 190 legitimately occupy wide boxes.
- Vertical-centre outlier checks can locate obvious row errors but cannot prove that dots, characters or cropped rows are correct. An empty outlier list is not a completed visual audit.
- Report unresolved errors explicitly. Do not mark a row or page Done after partial inspection. Flag unresolved rows when authorized, distinguishing a known problem from one merely not yet examined.

## Known browser-only limit: crop boundaries

The tested viewer renders strips from fixed `line_quad` bounds. Moving/deleting tokens and resizing saved boxes do not change those bounds. Its current browser controls expose no row-boundary editor.

Thus a character can be assigned to the correct row while fragments of that character still appear in a neighbouring image strip. State which of these is fixed. Do not claim that changing token ownership repaired clipping. Reinspect available controls if the app changes; do not modify application code or database records under a browser-review request without separate authorization.

## Page-190 trial record

These are local observations, not new universal Coptic rules or additions to the p010–p029 text-only training set:

| Displayed row | Action/status |
|---|---|
| 10 / 10.01 | Centred barred omicron–eta numeral separated from body text into a dedicated row; two new boxes resized; source numeral tokens removed; persistence checked. Fixed strip overlap remained. |
| 11 / 12 | Three question-mark tokens identified as separately recognized overlines removed while owning letters retained their bars. |
| 17 | Missing opening bracket before large initial `pi` added. |
| 21 | Four labels corrected to Latin `leer` using literal keyboard input. |
| 22 | Separate boxes added for final `e`, `t` and closing bracket. |
| 10–13, including 10.01 | Fixed-crop overlap left unresolved and flagged. |
| 15 | Initial reinspection failed. After the user suggested warning-first inspection, the sha diacritic warning led to visual confirmation of a missing underdot in the saved label (`ϣ` → `ϣ̣`). Identification only; no correction made during the follow-up. The eta line-ending warning remained unconfirmed as an error. |

The earlier pass was incomplete. Retain that failure and the user-guided recovery alongside the successful UI operations; do not describe the row as corrected or fully checked.

## Completion report

Keep the chat report short: displayed line, exact character/mark/box changed, persistence result, and unresolved issues. Use readable character names such as “mu with overline” or “iota with two dots” rather than relying on font rendering. Never claim page-wide accuracy from a handful of repairs.