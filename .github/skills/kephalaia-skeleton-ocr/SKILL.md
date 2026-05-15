---
name: kephalaia-skeleton-ocr
description: Read a Kephalaia manuscript row by scanning skeleton templates across the connected ink. Defines the standing principles for character identification under the v2 OCR pipeline. Use when working on `temp/projects/kephalaia_ocr_v2/char_separation/skeleton_match_ocr.py` or any successor that scans skeleton templates against a row of ink. Keywords: kephalaia, skeleton, ocr, EMD, distortion, identity, perfect fit, impossible distortion, iota, brackets, coverage, scan, left-to-right.
---

# Kephalaia skeleton-matching OCR — standing principles

This skill records the user's reasoning for how the scan must work. Read it before changing `skeleton_match_ocr.py`. Do not invent rules. Do not add penalties. Do not add guards. Follow these principles literally; the right behavior must arise from them naturally.

## What the scan does

Scan the row over connected ink, progressing left-to-right (or right-to-left — direction is symmetric, only progression matters). At every starting position, evaluate every template against the ink. Each template is sized to the row's body height and tested only within its identity-preserving width range. Pick the winner under the rules below, then **advance by the winner's post-distortion width** (the `char_w` value that was actually placed on the ink). Repeat to end of row.

**No rough estimates.** If the identity-preserving distortion range cannot produce a perfect fit, the scanner does not lower its standards. It uses the blob-anchored fallback in principle 14 — never a least-wrong guess.

## Standing principles (user's reasoning, verbatim in spirit)

1. **The skeletons are derived from this manuscript's own glyphs.**
   Therefore, on any given character's ink, only the real character can be a near-perfect fit. The framework is asymmetric: real-on-real fits perfectly; cross-character matches do not.

2. **A perfect fit always beats a rough estimate.**
   No penalties, no forcing. The right answer must arise from the geometry.

3. **Score = forward distance only.**
   The score is the mean distance from template polyline points to the nearest ink pixel. Lower is better. Reverse penalties (ink → template) are forbidden — they are a forcing mechanism that violates principle 2.

4. **Iota is just a stick, so it will get a perfect forward fit almost anywhere there is a vertical stroke.**
   This is fine. It is not a bug. Iota fitting iota's ink, and iota also fitting a vertical stroke inside ⲛ, are both real perfect fits.

5. **At most one or two characters should perfect-fit at any start position.**
   If the identity range is tight and the height is the row body, the geometry forbids most templates from fitting at all. The canonical case where two characters perfect-fit at the same x is **iota inside ⲛ**: the first vertical stroke of ⲛ is itself a perfectly good iota. Both forward-fit perfectly. The more complex character (ⲛ) wins because it explains more of the surrounding ink — see principle 6. Finding three or more perfect fits at one position is a signal that the identity range is too loose or the height is wrong.

6. **Among perfect fits at the same start position, the more complex character wins because it explains more of the connected ink.**
   Not "explains the whole blob." Just: the candidate that, within its own claim window, covers more of the actual surrounding connected ink. A complex character whose strokes all land on ink will explain more of the ink than a one-stroke iota landing on a single vertical inside it. The iota-vs-ⲛ case is the canonical example: iota fits the first stroke, ⲛ fits the first stroke AND the bowl AND the second stroke — ⲛ wins by coverage.

7. **More complex characters cannot be perfect on a true iota.**
   ψ on an iota's ink has its extra arm in empty space. υ missing an arm has the same problem in opposite sense. Their other strokes have nowhere to go. They fail the forward fit naturally — no extra rule is needed to disqualify them. Asymmetry is the engine: complex-on-simple fails forward; simple-on-complex passes forward but loses on coverage.

8. **Identity has limits — impossible distortion is forbidden by construction.**
   The skeletons are not point clouds. They are interconnected dots with rough geometric structure. The structure may distort, but cannot lose its meaning. Squishing iota wide enough to "fit" ⲛ, or stretching π narrow enough to "fit" iota, is an **impossible distortion**. This is bounded by the **width range [0.70..1.15] of the template's natural pixel width when it is scaled to the row's body height** — outside this range a template is not a candidate. The bound is structural, not a tunable penalty. A template that cannot perfect-fit anywhere inside its identity range simply does not match here.

9. **Height comes from the row body, not the column.**
   Every character on a line is rendered at the line's body height (from `geometry_rows[*]`). The template is scaled to that height first; its natural width follows from the scale. Then the width is allowed to flex within the identity range. Do NOT shrink the template to the local column's ink run — multi-stroke characters (ⲡ, ⲛ, ⲏ, ⲙ) have columns where only one stroke is present, and column-local height collapses the template to that stroke. The whole character is sized by the line, then evaluated against the full ink in its claim window.

10. **Coverage measures ink, not connected components.**
    "Explains more of the connected ink" means: of the ink pixels that lie inside the candidate's actual claim window (x..x+char_w × row_body_y_range), how many lie within a small tolerance of the template polyline? Counting connected-component bboxes is wrong because multi-stroke characters span multiple ink components. Coverage is over the ink itself.

11. **Advancement is by the winner's post-distortion width.**
    The winner has been placed at a specific scaled width inside the identity range. That `char_w` is what consumed the ink. The scanner advances by exactly that — not by the template's natural width, not by the connected-component width, not by a fixed step. The geometry of what was just identified dictates how much progress was made.

12. **Tiebreak is widest coverage. No invented composite metric.**
    - Build the set of all candidates with forward distance ≤ small perfect-fit threshold (~0.5 px).
    - Within that set, the candidate with the most ink covered wins.
    - If two candidates tie on coverage, the lower forward distance wins.
    - Advance by the winner's `char_w`.

13. **No perfect fit → blob-anchored fallback, NOT a rough guess.**
    A "blob" here means: a maximal run of connected ink in the row, isolated from its neighbors by clear whitespace. Whitespace boundaries are real and stable; they are the strongest structural anchor available when point-level fits fail. When no template in identity range perfect-fits at the current start position:

    a. Identify the current blob (the connected-ink run that contains or begins at the start position).
    b. Try to fit complex templates *anchored on the blob's bounding box* — that is, with their full width spanning a candidate sub-range of the blob, still under the identity-range width constraint. The blob's left and right edges constrain placement; impossible dimensions remain forbidden.
    c. If a complex template now perfect-fits when anchored against the blob edges, accept it. Advance by its `char_w`.
    d. If nothing perfect-fits even with blob anchoring, emit `?` for one column and advance by one pixel. Never lower the perfect-fit threshold. Never accept a least-wrong guess.

    The reasoning: a complex character that is *almost* aligned at a point-based start can be exactly aligned when its envelope is matched to the blob's envelope. The blob structure is doing real anchoring work, not estimation. Impossible distortions are still rejected. The fallback either yields another perfect fit or it yields `?` — there is no third option.

14. **Identity-class confusions that are acceptable.**
    Confusing iota `ⲓ` with bracket `[` or `]` is managable downstream — they are all thin verticals. The unforgivable failure is **missing iotas/brackets entirely** by letting a wider wrong template win, or **matching iota when the ink is clearly a wider character** (ⲛ, ⲏ).

15. **No ground truth in the system.**
    The only ground truth is the manuscript image. The LLM witness (`output/projects/kephalaia_v2/pages/p_NNN.json`) is a rough hint at most — never a target. Do not compare OCR output to the witness Coptic text. Validate by rendering the row review sheet over the manuscript and looking.

## Forbidden patterns

These have all been tried and they all break principle 2:

- Reverse-direction EMD as a penalty against wide templates claiming empty space.
- Per-column local height for sizing the template.
- Coverage based on connected-component bboxes instead of ink pixels.
- "Composite" scores that combine forward and reverse to disqualify candidates.
- Preemptive guards: "skip if narrow component," "skip if already inside component," "skip if x < start_component.x0," `matchable` filters.
- Fallback to lowest-composite candidate when no candidate passes the perfect-fit threshold.

If you find yourself adding any of these, stop. The behavior you want must arise from principles 1–15.

## Allowed parameters

- `FORWARD_THRESHOLD` — the cutoff for "perfect fit" in pixels of mean forward distance. Empirical, tunable.
- `WIDTH_SCALE_MIN`, `WIDTH_SCALE_MAX` — the identity range. Currently [0.70, 1.15]. Tighter is safer; wider invites impossible distortion.
- Row body height comes from `geometry_rows[i]` (use `bbox` height or median-line/baseline span). One height per row, applied to every template on that row.

## Diagnostic workflow

When a character is misread, do this in order:

1. View the row review sheet over the manuscript. Look at the exact x range that's wrong.
2. Run a probe script (`temp/probe_row_X.py` pattern) that lists every template candidate at that x with `(forward, char_w, coverage)`. Read the numbers.
3. Confirm the real character is in identity range and would fit forward ≤ FORWARD_THRESHOLD. If not, the template or the width range is the problem.
4. Confirm coverage measurement actually counts ink pixels in the claim window, not component bboxes.
5. If the right character is in the perfect-fit pool but loses on coverage, fix the coverage computation, not the score.

## File anchors

- Engine: [temp/projects/kephalaia_ocr_v2/char_separation/skeleton_match_ocr.py](temp/projects/kephalaia_ocr_v2/char_separation/skeleton_match_ocr.py)
- Row geometry: `temp/projects/kephalaia_ocr_v2/body_geometry/out/pages/p<NNN>_geometry.json`
- Templates: `temp/projects/kephalaia_ocr_v2/glyph_seed_library/manual_template_line_profiles/*.json`
- Review sheet output: `temp/projects/kephalaia_ocr_v2/skeleton_ocr/p<NNN>_review.png`
- The LLM witness (NOT ground truth, hint only): `output/projects/kephalaia_v2/pages/p_<NNN>.json`
