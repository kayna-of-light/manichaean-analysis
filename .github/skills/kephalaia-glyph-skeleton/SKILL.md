---
name: kephalaia-glyph-skeleton
description: Derive a clean single-line pen-stroke skeleton for one Coptic character of the Kephalaia manuscript. The workflow goes one character at a time. For each target glyph, draw a wide net of candidates from the v2 body crops, render an indexed atlas, visually triage at high zoom, hand-pick 20 verified specimens spread across the manuscript, then synthesize one skeleton by pixel-vote over normalized cutouts. Outputs go to `temp/projects/kephalaia_ocr_v2/glyph_seed_library/per_char/<slug>/` and the family JSON is written to `manual_template_line_profiles/` so that `glyph_seed_workflow.py character-sheet --include-special` picks it up. Use when asked to derive a skeleton for a Coptic character, build a glyph seed family, or regenerate the character review sheet with a new character. Keywords: kephalaia, skeleton, glyph, gangia, ϫ, ⲉ, ⲱ, ⲧ, cutout, atlas, synthesize, single-line trace, per-character workflow.
---

# Kephalaia per-character skeleton derivation

## Standing principles

1. **One character at a time.** Do not try to scale up before the current character is solved. The user is explicit about this.
2. **Cutouts come ONLY from the current v2 body crops.** Image data must be sourced from `output/projects/kephalaia_ocr_v2/line_body_split/text_body/pNNN_text_body.jpg` using the polygons in `output/projects/kephalaia_ocr_v2/body_geometry/pages/pNNN_geometry.json`.
3. **LLM witness transcription is the PRIMARY localization source.** Per-line Coptic text lives in `output/projects/kephalaia_v2/pages/p_NNN.json`. When a witness line has no `{N}` apparatus placeholders AND its letter count matches the geometry row's component count, you have a 1-to-1 letter↔component map for that line — true ground truth. Run `harvest_witness_labels.py` once per character workflow to materialize this map.
4. **Old cluster data (`output/projects/kephalaia_ocr/clusters_shape_padded_split_bodycrop_corrected_k240/`) is a FALLBACK pointer only.** It works for visually distinctive shapes (ϫ X-shape was clean enough) but fails for characters with lookalikes (ⲉ collides with ⲥ, ⲏ, ⲟ, ⲛ). Never trust it without manuscript-context verification. Never consume its PNG cutouts.
5. **Show the user what you produced.** Every step that yields a sheet should be followed by viewing the sheet so the user can audit it.

## Inputs you can rely on

- `temp/projects/kephalaia_ocr_v2/char_separation/cutout_and_skeleton.py` — shared library of helpers: candidate loader, v2 component matcher, polygon-mask cutter, Otsu binarizer, Zhang-Suen thinning, skeleton vectorizer, `V2Match`, `load_old_candidates`, `find_v2_component`, `cut_glyph`, `cutout_to_image`, `skeleton_overlay_image`, `select_spread`, `vectorize_skeleton`, `zhang_suen_thin`.
- `temp/projects/kephalaia_ocr_v2/char_separation/harvest_witness_labels.py` — **witness harvester (primary localization)**. Reads `output/projects/kephalaia_v2/pages/p_*.json`, skips lines with `{N}` placeholders, accepts lines where stripped Coptic-letter count equals the geometry row's component count, and writes a per-letter map to `temp/projects/kephalaia_ocr_v2/glyph_seed_library/witness_labels.json`. As of the ⲉ run: 270 clean lines across 282 pages, ~1000 instances for the most common letters (ⲉ=1092, ⲁ=1004, ⲛ=902, ⲧ=759, ⲙ=557, ...).
- `temp/projects/kephalaia_ocr_v2/char_separation/eie_witness_verify.py` — **witness-driven verify sheet template (ⲉ)**. Reads `witness_labels.json`, spreads ground-truth instances across pages, renders them at 8× zoom with index labels for hand-picking. Use this as the template for any new character with lookalikes.
- `temp/projects/kephalaia_ocr_v2/char_separation/gangia_atlas.py` — fallback atlas template (cluster-pointer route, ϫ only — only for visually distinctive characters that have been verified to cluster cleanly).
- `temp/projects/kephalaia_ocr_v2/char_separation/gangia_verify_picks.py` — pattern for high-zoom verification of an index list (works for either route).
- `temp/projects/kephalaia_ocr_v2/char_separation/synthesize_base.py` — **common base class** for all per-character synthesis. Contains `GlyphSynthesizer` (base), `WitnessSynthesizer` (single atlas JSON), and `ClusterSynthesizer` (per-seed atlas JSONs). Also exports `normalize()`, `render_skeleton_panel()`, `render_grey()`, `write_template_family()`, and constants (`CANVAS=80`, `GLYPH_FIT=64`, `VOTE_THRESHOLD=0.50`, `MAX_FILTER_SIZE=3`, `MIN_POLYLINE_PIXELS=4`). All per-character scripts subclass one of these and define only `CHAR`, `PICKS`, and atlas config.
- `temp/projects/kephalaia_ocr_v2/char_separation/gangia_synthesize.py` / `eie_synthesize_v2.py` — examples of `ClusterSynthesizer` and `WitnessSynthesizer` subclasses respectively.

The Python entry point is always `& "$env:USERPROFILE\.conda\envs\manichaean\python.exe"` from the repo root. Add `-W ignore` to suppress Pillow `mode=` deprecation noise.

## Workflow

### Step 0 — Pick the next target character

Coordinate with the user. Do not start a new character without consent. Each character has its own slug `u<codepoint>` (e.g. `u03eb` for ϫ).

### Step 1 — Harvest the LLM witness (if not already done this session)

Run once per workflow session:

```powershell
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" -W ignore temp/projects/kephalaia_ocr_v2/char_separation/harvest_witness_labels.py
```

This writes `temp/projects/kephalaia_ocr_v2/glyph_seed_library/witness_labels.json` with schema:

```
{
  "counts": { "ⲉ": 1092, "ⲁ": 1004, ... },
  "stats":  { "pages": 282, "lines_total": 9505, "lines_clean": 270, ... },
  "by_letter": { "ⲉ": [ { "page": "053", "row_index": 2, "component_id": 1247, "bbox": [...] }, ... ] }
}
```

Confirm the target letter has ≥30 instances. If it does, take the **witness route** (Step 2a). If the letter is too rare in clean lines, fall back to the **cluster route** (Step 2b) — but verify aggressively at step 3.

### Step 2a — Witness-driven verify sheet (PRIMARY route)

Copy `eie_witness_verify.py` to `<slug>_witness_verify.py`. Set `CHAR = "<glyph>"`. Run:

```powershell
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" -W ignore temp/projects/kephalaia_ocr_v2/char_separation/<slug>_witness_verify.py --count 64 --seed 1 --name witness_verify
```

This spreads 64 ground-truth instances across pages and renders them at 8× zoom into `temp/projects/kephalaia_ocr_v2/glyph_seed_library/per_char/<slug>/witness_verify.png` plus its indexed JSON. Every cell IS the target letter (alignment-confirmed); your only job is to filter for clean strokes (skip damaged/connected/ink-bled instances). Pick ~20 spread across the manuscript.

Skip Step 2b.

### Step 2b — Cluster-pointer atlas (FALLBACK route, only when witness is insufficient)

Copy `gangia_atlas.py` to `<slug>_atlas.py`. Adjust:

- `CHAR = "<the target glyph>"`
- `W_MIN, W_MAX, H_MIN, H_MAX` — bbox bounds for the target. Read from sample bboxes in `_assignments.json`, or run unfiltered first.

Run:

```powershell
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" -W ignore temp/projects/kephalaia_ocr_v2/char_separation/<slug>_atlas.py --seed 1 --name candidate_atlas
```

The atlas script writes `candidate_atlas.png` and `candidate_atlas.json` into the per-char directory. **Expect heavy contamination on any character with visual lookalikes.** Use only if you've confirmed (by manuscript probe) that the cluster is clean for this character.

### Step 3 — Synthesize

All synthesize scripts inherit from `synthesize_base.py`. Create `<slug>_synthesize.py` with ~15 lines:

**Witness route (preferred):**

```python
from synthesize_base import WitnessSynthesizer

class MySynthesizer(WitnessSynthesizer):
    CHAR = "<glyph>"
    ATLAS_JSON_NAME = "witness_verify.json"
    _PICKS_INDICES = [1, 3, 5, ...]  # indices from witness_verify.json
    PICKS: list[tuple[int, int]] = [(1, i) for i in _PICKS_INDICES]

if __name__ == "__main__":
    MySynthesizer().run()
```

**Cluster route (fallback):**

```python
from synthesize_base import ClusterSynthesizer

class MySynthesizer(ClusterSynthesizer):
    CHAR = "<glyph>"
    PICKS: list[tuple[int, int]] = [(1, 0), (1, 3), (2, 14), ...]
    ATLAS_JSON = {1: "candidate_atlas.json", 2: "candidate_atlas_s2.json"}

if __name__ == "__main__":
    MySynthesizer().run()
```

**Synthesis methodology (fixed in base class, do not override):**

- Vote on **thick ink** (not 1px skeletons — 1px skeletons fragment curves due to sub-pixel alignment jitter)
- `VOTE_THRESHOLD = 0.50` — true median: a pixel must appear in ≥50% of specimens
- `MAX_FILTER_SIZE = 3` — bridges 1-2px alignment jitter only (MaxFilter(5) fills structural gaps and creates topology not in any specimen)
- Zhang-Suen thin the voted ink to a single-pixel skeleton
- Vectorize into polylines, drop spurs shorter than `MIN_POLYLINE_PIXELS = 4`

The synthesis IS the median of the specimens. If it doesn't look like the specimens, something is wrong with the picks, not the pipeline.

Run:

```powershell
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" -W ignore temp/projects/kephalaia_ocr_v2/char_separation/<slug>_synthesize.py
```

This writes:

- `temp/projects/kephalaia_ocr_v2/glyph_seed_library/per_char/<slug>/final_skeleton.png` — review sheet: hero panel with synthesized skeleton + grid of 20 normalized cutouts and per-sample skeletons.
- `temp/projects/kephalaia_ocr_v2/glyph_seed_library/per_char/<slug>/final_skeleton.json` — vectorized polylines + sample metadata.
- `temp/projects/kephalaia_ocr_v2/glyph_seed_library/manual_template_line_profiles/<slug>_line_profile_family.json` — the family file consumed by the master sheet.

View `final_skeleton.png`. The synthesized skeleton should look like the median of the 20 specimens.

If the skeleton doesn't match the specimens:
- **Contaminant in picks** → the most likely cause. Return to step 2 and replace the bad pick.
- **Minor 1-2px gaps** → acceptable; MaxFilter(3) bridges these. Do NOT increase to MaxFilter(5).
- **Crooked alignment** → check the alignment in `normalize()`. We bbox-fit + centroid-align vertically; rotational alignment is not needed because the manuscript is already deskewed.

**Do NOT tune VOTE_THRESHOLD or MAX_FILTER_SIZE per character.** These are fixed at 0.50 and 3 respectively. If the result looks wrong, the picks are wrong.

### Step 4 — Regenerate the master character sheet

```powershell
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" -W ignore temp/projects/kephalaia_ocr_v2/char_separation/glyph_seed_workflow.py character-sheet --include-special
```

This regenerates `temp/projects/kephalaia_ocr_v2/glyph_seed_library/review_sheets/character_skeleton_review_sheet.png`. The new family JSON is picked up automatically; the cell for the target character will now show the synthesized skeleton instead of "missing skeleton". View the master sheet so the user can see the progress.

### Step 5 — Hand back to the user

Report:
- The target character (Unicode + Latin name).
- How many candidates were considered, how many were rejected and why.
- The synthesized skeleton stats (px count, polyline count).
- Link to `final_skeleton.png` and the regenerated master sheet.

Ask whether to proceed to the next character or polish the current one further.

## Common pitfalls

- **Skipping the witness harvest.** It is the ground truth. The cluster-pointer route looks faster but burns hours on contaminant cleanup for any character with lookalikes (ⲉ, ⲥ, ⲏ, ⲟ, ⲛ all collide; small letters like ⲓ are even worse). The ⲉ pipeline lost a full iteration to this — first three atlases were dominated by ⲥ/ⲏ.
- **Picking from a thumbnail atlas without manuscript verification.** Always render the verify sheet at 8× before committing to picks. The thumbnails hide 1-2 contaminants per 20 picks even on the witness route (damaged/connected glyphs sneak through).
- **Picking a component by bbox alone, not by `component_id`.** When loading a verified sample, always use the exact `component_id` saved in the atlas/witness JSON, not a re-derived row-scan. Picking by row + bbox heuristics finds a *different* component on most pages (usually the widest, often ⲱ or a connected blob).
- **Trusting `_char_assignments_projected.json` as ground truth.** It is a majority-vote cluster label, not a per-blob label. Witness-aligned letters are real ground truth; cluster labels are not.
- **Pulling cutouts from the old project's PNGs.** Don't. Always cut from the current v2 body crop via the polygon mask.
- **Forgetting to view the result.** Every sheet should be viewed and reported back to the user. The user explicitly called this out.

## File map

| Path | Purpose |
|------|---------|
| `temp/projects/kephalaia_ocr_v2/char_separation/cutout_and_skeleton.py` | Shared helpers |
| `temp/projects/kephalaia_ocr_v2/char_separation/harvest_witness_labels.py` | Witness harvester (run once per session) |
| `temp/projects/kephalaia_ocr_v2/char_separation/eie_witness_verify.py` | Witness-driven verify-sheet template (ⲉ) |
| `temp/projects/kephalaia_ocr_v2/char_separation/synthesize_base.py` | **Common base class** — `GlyphSynthesizer`, `WitnessSynthesizer`, `ClusterSynthesizer` |
| `temp/projects/kephalaia_ocr_v2/char_separation/eie_synthesize_v2.py` | Witness-route example (ⲉ, subclasses `WitnessSynthesizer`) |
| `temp/projects/kephalaia_ocr_v2/char_separation/gangia_synthesize.py` | Cluster-route example (ϫ, subclasses `ClusterSynthesizer`) |
| `temp/projects/kephalaia_ocr_v2/char_separation/gangia_atlas.py` | Cluster-route atlas template (ϫ, fallback) |
| `temp/projects/kephalaia_ocr_v2/char_separation/gangia_verify_picks.py` | Cluster-route verification template (ϫ, fallback) |
| `temp/projects/kephalaia_ocr_v2/char_separation/glyph_seed_workflow.py` | Master sheet builder |
| `temp/projects/kephalaia_ocr_v2/glyph_seed_library/witness_labels.json` | Per-letter ground-truth map |
| `temp/projects/kephalaia_ocr_v2/glyph_seed_library/per_char/<slug>/` | Per-character artefacts |
| `temp/projects/kephalaia_ocr_v2/glyph_seed_library/manual_template_line_profiles/<slug>_line_profile_family.json` | Family JSON consumed by master sheet |
| `temp/projects/kephalaia_ocr_v2/glyph_seed_library/review_sheets/character_skeleton_review_sheet.png` | Master sheet output |

## Reference examples

### ϫ gangia (cluster route — character had no lookalikes)

- 96-candidate atlas at seed 1 and seed 2.
- 20 verified picks across pages 010–230, all X-shaped with bbox 18–26 × 14–22 px.
- Synthesis: 153 skeleton px, 49 polylines (junction spurs trimmed to 16 strokes in the family file via `MIN_POLYLINE_PIXELS = 4`).
- Master sheet cell for ϫ shows the canonical X with horizontal foot.

### ⲉ epsilon (witness route — taught us why cluster pointer fails)

- First attempt used cluster pointer → atlases mixed ⲥ, ⲏ, ⲟ, ⲛ. Confirmed contamination by rendering manuscript-context probes (`eie_probe_neighbors.py`: p268 idx41 was ⲥ, p053 idx28 was ⲏ).
- Pivoted to witness harvest → 1092 ground-truth ⲉ instances across 270 clean lines on 282 pages.
- Witness verify sheet showed all 63 rendered cells were genuine ⲉ (closed-C with middle bar).
- 19 visually-confirmed picks → synthesis: 85 skeleton px, 13 polylines.
- Master sheet cell now shows the canonical C-with-middle-bar form.
