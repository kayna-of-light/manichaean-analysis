---
name: kephalaia-page-reading
description: Read a page image of the printed Kephalaia edition (Polotsky/Böhlig) by eye, verify every gap count, sublinear dot and supralinear stroke by measurement, and record it as an EpiDoc TEI page with derived analysis layers and a line-aligned print. Use when asked to read, transcribe, digitise, verify, correct, encode or print Kephalaia pages, or to work with data/kephalaia/epidoc or output/projects/kephalaia_reading. Keywords: kephalaia, page image, read, transcribe, Coptic, Leiden, EpiDoc, TEI, lacuna, gap, unclear, supplied, supralinear, overline, diaeresis, ekthesis, kephalaion, apparatus, layers, print.
---

# Kephalaia page reading

You read the page yourself. The page image is the only authority. Do not consult the OCR pipelines, model
transcriptions, review exports, page JSON, glyph libraries, translations or any older skill output in this repo.

| What | Where |
|---|---|
| Page images (edition pp. 10–291) | `output/projects/kephalaia_v2/coptic/images/keph_pNNN.jpg` (1553×2258) |
| Tools | `scripts/projects/kephalaia_reading/` (`model.py` is shared by all of them) |
| Drafts, crops (working files) | `temp/kephalaia_reading/drafts/keph_pNNN.txt`, `temp/kephalaia_reading/crops/` |
| **Canonical record** | `data/kephalaia/epidoc/keph_pNNN.xml` (EpiDoc TEI, tracked) |
| Analysis layers (rebuildable) | `output/projects/kephalaia_reading/layers/` |
| Print (rebuildable) | `output/projects/kephalaia_reading/print/` |

Run every tool from `scripts/projects/kephalaia_reading/`.

## What the page shows

The scan is of the printed edition, not of the manuscript. Its sigla are the editors' and are reproduced exactly:

- Coptic in a font where ⲓ is a bare stroke, ϥ and ϩ have descenders, and ⲯ (arms curved up) differs from ϯ.
- `[ ]` lost and restored · `[. . .]` lost, one dot per letter · `. . .` illegible, one dot per letter ·
  a dot under a letter means uncertain · `[ⲁⲃ?]` uncertain restoration.
- Supralinear strokes over single letters, and continuous strokes over ⲙⲛ, ⲛⲛ, nomina sacra (ⲡⲛⲁ, ⲓⲏⲥ, ⲙⲛⲭⲥ),
  numerals and the framed manuscript page number. Diaereses on ⲓ. In this font the stroke over ⲥ and ϩ is printed obliquely.
- Enlarged initials, lines in ekthesis (outdented), page-head ornaments `>·` `·<`, end mark `:—`.
- Chapter openings: a centred numeral (ⲙ̅ⲅ̅ = 43), a title line or two, and the numeral again in both margins.
- German in the edition (running head `Kap. XLIII: …`, the word `leer`, footnotes) is **never transcribed**.
  Its content is encoded as structure (table below). Footnote line numbers can be wrong: the printed margin
  numerals decide which line is meant.

## Workflow

1. **Bands and numbering.** `python measure.py bands NNN` lists line bands; their centres become the line
   y-values. Count lines against the printed margin numerals, with `zoom` on x 370–700 to see them.
   Merged bands (headings) and lines of dots only can be missing from the list; take those y-values from a zoom.
2. **Read.** `python measure.py zoom NNN NAME 1.6 y0:y1:440:1430 ...` for full-width sheets of about 12 lines,
   2–3.6× for halves, 4–8× for single words. View **one image per call**. Images are dropped from context
   later, so write each line into the draft right after viewing it. Never write a reading you have not seen.
3. **Draft.** One row per printed line, in the markup below.
4. **Verify by measurement.** These checks decide; your eye proposes.
   - Gap counts: `measure.py dots NNN y0 y1 x0 x1` on the row; count the blobs on the baseline.
   - Sublinear dots: `measure.py assign …` puts `*` on every glyph with a blob under it. Real dots are about 7–15 px
     in area; 1–2 px specks are noise. The dot under ϥ, ϩ (and ϣ, ⲣ) sits just **left of the descender**:
     undotted ϥ/ϩ produce no blob at all (checked against controls), so a blob there is a real dot.
   - Strokes: `measure.py strokes …` gives each glyph the percentage covered. A stroke belongs to every letter it
     covers by **at least half** that letter's width (single letter → `-`, two or more → `+`). The detector misses
     strokes touching a letter (ⲃ̄) and can mistake the top hook of ϥ for a stroke: zoom on both cases.
   - Overlines over numerals and nomina sacra: measure them too. The printed extent can stop short (p. 183 l. 13).
   - Diaeresis: two dots above ⲓ; look at 4× when a dot list shows paired blobs above the line.
   - Ekthesis and enlarged letters: compare line starts in a margin strip.
5. **Compile.** `python compile_draft.py ../../../temp/kephalaia_reading/drafts/keph_pNNN.txt` writes the TEI.
   Once compiled, the **TEI is canonical**: later corrections go into the XML. `--force` recompiles from the draft
   and discards XML edits.
6. **Validate.** `python validate.py NNN --drafts ../../../temp/kephalaia_reading/drafts` checks the element profile,
   numeral values, facsimile zones, contiguous lines, and that draft → TEI → Leiden is identical character for character.
7. **Reconcile.** `python measure.py reconcile NNN` compares dots per line (sublinear + gap dots) on the image
   with the reading. Explain every flagged line. Known harmless flags: the word "leer", the colon of `:—`, dots under the
   area threshold, a ϣ tail.
8. **Layers and print.** `python layers.py` and `python render_print.py NNN ...`. Then look at
   `print/preview_N.png` side by side with the scan. The aligned view catches what line-by-line reading misses
   (ekthesis, a missing dot, a misplaced heading).

## Draft markup → Leiden → EpiDoc

| Draft | Leiden | EpiDoc |
|---|---|---|
| `[ⲁⲃ]` | [ⲁⲃ] | `<supplied reason="lost">` |
| `[ⲁⲃ(?)]` | [ⲁⲃ(?)] | `<supplied reason="lost" cert="low">` |
| `[....]` | [....] | `<gap reason="lost" quantity="4" unit="character"/>` |
| `....` | .... | `<gap reason="illegible" quantity="4" unit="character"/>` |
| `ⲁ_` | ⲁ̣ | `<unclear>` |
| `ⲛ-` | ⲛ̄ | `<hi rend="supraline">` (one letter) |
| `ⲙ+ⲛ+` | ⲙ̅ⲛ̅ | `<hi rend="supraline">` spanning the letters |
| `ⲥ'` | ⲥ̀ | `<hi rend="supraline" rendition="#oblique">` |
| `ⲓ*` | ⲓ̈ | `<hi rend="diaeresis">` |
| `^ⲡ` | enlarged | `<hi rend="large">` |
| `⟨ⲡ⟩` | ⟨ⲡ⟩ | `<supplied reason="omitted">` |
| `{ⲧⲉ}` | {ⲧⲉ} | `<surplus reason="repeated">` |
| `\ⲙⲁϩ/` | \ⲙⲁϩ/ | `<add place="above">` |
| `«ϫⲱⲩ»` | ϫⲱⲩ | `<sic>` |
| `vac.` | vac. | `<space extent="unknown" unit="character"/>` |
| `%` | wide blank | `<space type="unmarked" …/>` (blank the editors do not mark) |
| `>` `<` `·` `§` `‡` | >  <  ·  :—  ] | `<g type="diple">`, `diple-reversed`, `middot`, `dicolon-dash`, `unpaired-bracket` |

Combine marks in this order after a letter: `_` then `*` then `-`/`+`/`'` (e.g. `ⲣ_-`, `ⲥ_+`).
Spaces are the edition's word division (Coptic is scriptio continua); keep them exactly as printed.

Draft rows (see the `compile_draft.py` docstring):

```
page 111
continues 42
pagenum 208 | ⲣ[ⲓ]ⲁ
header 250 | [> ·]ⲙ-ⲡⲥⲁϩ · <
9 630 | {ⲧⲉ} ⲛⲓϩⲃⲏⲩⲉ ⲉⲧ[ϫ]ⲁϩⲙⲉ ⲟⲩⲱⲛϩ «ϫⲱⲩ» ϩⲛ- ⲛⲉ_ϥ_ ....
18 1008 number kephalaion=43 | ⲙ+ⲅ+
19 1053 title | >· ⲉⲧⲃⲉ ⲙ-ⲙⲁⲛϫⲓⲟⲟⲣⲉ ·<
margin 19 1053 left | ⲙ+ⲅ+
20 1098 ekthesis | [^ⲡⲁ]ⲗ_ⲓⲛ ⲁⲛ ⲁ ⲙⲙⲁⲑⲏⲧⲏⲥ ...
note 9 | English note on an editorial or printing fact.
```

## The editors' German, as structure

| On the page | Encode as |
|---|---|
| running head `Kap. N: title` | nothing; `<milestone unit="kephalaion" n="N"/>` from the Coptic numeral, `continues N` for the chapter in progress |
| `leer` | `vac.` → `<space/>` |
| footnote `Lies ⟨x⟩y` / `Lies <word>` with letters missing | `⟨x⟩` → `<supplied reason="omitted">` |
| `Dittographie` | `{x}` → `<surplus reason="repeated">` |
| `über der Zeile (nachgetragen)` | `\x/` → `<add place="above">` |
| `sinnlos`, `Schreibfehler` with no correction | `«x»` → `<sic>` |
| `[x?]` | `[x(?)]` → `@cert="low"` |
| anything else worth keeping | `note N |` in English → `<div type="commentary">` |

## Analysis layers

`layers.py` writes `layers/pages/keph_pNNN.json` and corpus tables `lines`, `words`, `letters`, `strokes`, `gaps`,
`blanks`, `signs`, `corrections`, `notes` (`.csv`). Every row carries `page` and `line`. Letters carry `i` (index in
the line), `status` (certain · unclear · restored · omitted · surplus · added-above), `cert`, `word`, `stroke`,
`stroke_kind`, `diaeresis`, `large`, `sic`, `kephalaion`. Gaps, blanks and signs carry `before_letter`. Lines carry
`leiden`, `diplomatic` (what the manuscript shows: no spaces, `·` per lost or illegible letter), `reading` (all
letters incl. restorations, no diacritics, word spaces), `ekthesis`, `zone`, `type`, `kephalaion`.
The page JSON adds the page number, running title, kephalaia with title lines, and the margin numerals.

## Reporting

Say what was measured and what rests on your eye. Never claim 100 %. The usual residual risks are a single-letter
stroke or a diaeresis. List every editorial decision you made (wrong footnote numbering, printing anomalies kept as printed).
