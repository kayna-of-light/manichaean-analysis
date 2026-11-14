---
name: kephalaia-page-reading
description: Read a page image of the printed Kephalaia edition (Polotsky/Böhlig) by eye, verify every gap count, sublinear dot and supralinear stroke by measurement, and record it as an EpiDoc TEI page with derived analysis layers and a line-aligned print. Use when asked to read, transcribe, digitise, verify, correct, encode or print Kephalaia pages, or to work with data/kephalaia/epidoc or output/projects/kephalaia_reading. Keywords: kephalaia, page image, read, transcribe, Coptic, Leiden, EpiDoc, TEI, lacuna, gap, unclear, supplied, supralinear, overline, diaeresis, ekthesis, kephalaion, apparatus, layers, print.
---

# Kephalaia page reading

You read the page yourself. The page image is the only authority. Do not consult the OCR pipelines, model
transcriptions, review exports, page JSON, glyph libraries, translations or any older skill output in this repo.

**The ledger comes first.** `docs/KEPHALAIA_READING_LEDGER.md` is the project's running record: page status, method
lessons (§3) and encoding decisions (§4). Read it in full before any page. Where the ledger and this skill differ, the
ledger wins. When a session meets a case neither covers, it decides it and writes the decision into the ledger, so the
next session encodes it the same way; a "we should consider …" with no decision is not allowed. A lesson that holds for
every page belongs in this skill as well, and a session may update the skill, the vocabulary and the tools when that makes
the results more stable (separate commit, logged in ledger §6).

| What | Where |
|---|---|
| Page images (edition pp. 10–291) | `output/projects/kephalaia_v2/coptic/images/keph_pNNN.jpg` (1553×2258, git-ignored). If missing, download the same file names from the Google Drive folder https://drive.google.com/drive/folders/1OIO3H2-nzmgHsSnNAEXyrDRmsL7BaEwi into that directory |
| Tools | `scripts/projects/kephalaia_reading/` (`model.py` is shared by all of them) |
| Drafts, crops (working files) | `temp/kephalaia_reading/drafts/keph_pNNN.txt`, `temp/kephalaia_reading/crops/` |
| **Canonical record** | `data/kephalaia/epidoc/keph_pNNN.xml` (EpiDoc TEI, tracked) |
| Analysis layers (rebuildable) | `output/projects/kephalaia_reading/layers/` |
| Review images (tracked) | `data/kephalaia/review/keph_pNNN.jpg`, from `review_images.py` |
| Editorial vocabulary (tracked) | `data/kephalaia/editorial_vocabulary.json`: every German formula of the editors → one id |
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
- German in the edition (running head `Kap. XLIII: …`, the word `leer`, the statements in the text block,
  footnotes) is **never transcribed**. Its meaning is encoded as structure through the editorial vocabulary
  (section below). Footnote line numbers can be wrong: the printed margin numerals decide which line is meant.

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
   - Strokes: `measure.py strokes …` finds the bars. A stroke belongs to every letter it covers by **at least half**
     that letter's width (single letter → `-`, two or more → `+`). The `strokes` percentages overstate coverage (the
     detector merges a bar with neighbouring ink): for every stroke over two letters, read the bar's x-extent on its
     densest pixel row (grey < 130) and each letter's ink extent in the x-height band, and decide on those numbers. The
     detector misses strokes touching a letter (ⲃ̄), reports descenders of the line above, and can mistake the top hook
     of ϥ for a stroke: zoom on all three cases.
   - Dotted ϣ: some ϣ carry a separate dot in the lower bowl. Look at every ϣ (a sheet of the band y−12…y+14 of each
     line at 2.4–2.6× shows them all) and confirm each dotted one at 8× beside an undotted ϣ on the same page.
   - Overlines over numerals and nomina sacra: measure them too. The printed extent can stop short (p. 183 l. 13).
   - Diaeresis: two dots above ⲓ; look at 4× when a dot list shows paired blobs above the line.
   - Ekthesis and enlarged letters: compare line starts in a margin strip.
5. **Compile.** `python compile_draft.py ../../../temp/kephalaia_reading/drafts/keph_pNNN.txt` writes the TEI.
   Once compiled, the **TEI is canonical**. To correct a page later, `python decompile.py NNN` writes its draft back
   from the TEI (exact round trip), edit the draft, and recompile with `--force`; or edit the XML directly.
6. **Validate.** `python validate.py NNN --drafts ../../../temp/kephalaia_reading/drafts` checks the element profile,
   numeral values, facsimile zones, contiguous lines, and that draft → TEI → Leiden is identical character for character.
7. **Reconcile.** `python measure.py reconcile NNN` compares dots per line (sublinear + gap dots) on the image
   with the reading. Every flagged line must be explained by exact positions or the reading corrected; never pad a run.
   It counts only blobs of area ≥ 6 whose top lies ≥ 2 px below the zone centre, so these flag without an error: dots
   of area < 6, dots at line-centre height, a dot inside a letter's box (a dotted ϣ's bowl dot, a dot joined to the
   letter), a dotted letter inside a restoration, printed punctuation (`:`, `.`, the colon of `:—`), the word "leer",
   and letter feet in title lines. A flag is never explained by "a ϣ tail": look at the ϣ at 8×.
8. **Layers and print.** `python layers.py` and `python render_print.py NNN ...`. Then look at
   `print/preview_N.png` side by side with the scan. The aligned view catches what line-by-line reading misses
   (ekthesis, a missing dot, a misplaced heading).
9. **Review images.** `python review_images.py NNN` renders `data/kephalaia/review/keph_pNNN.jpg` from the layers
   JSON. It shows the scan on the left and the reading line for line on the right, with kephalaion, counts, apparatus
   and notes. It is meant for the user's direct visual inspection: commit it with the page. In a report, link it as
   `https://raw.githubusercontent.com/kayna-of-light/manichaean-analysis/<commit-sha>/data/kephalaia/review/keph_pNNN.jpg`
   (the repo is public; pin the SHA so the image never changes under the link).

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
| `⟦ⲡⲙⲩⲥⲧⲏⲣⲓⲟⲛ⟧` | ⟦…⟧ | `<del rend="expunction">` (deleted by the scribe; the edition prints [[ ]]) |
| `⁅=destroyed⁆` | [---] / --- | `<gap reason=… extent="unknown" unit="character" ana="#ed.destroyed"/>` (editors' statement) |
| `⁅=illegible:line⁆` | ------ | `<gap reason="illegible" quantity="1" unit="line" ana="#ed.illegible"/>` (the whole line) |
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
note 9 print | English note on a printing fact (category from the vocabulary's "tr" list).
app 13 conjecture | | [ⲡ]ⲁⲛⲉⲥ | for the beginning of the line, perhaps
app 24 correction printed=23 | | ⟨ⲡ⟩ⲡ+ⲛ+ⲁ+ | read
```

## The editors' German, as structure

`data/kephalaia/editorial_vocabulary.json` maps every German formula the editors use to one id and records the
judgement behind it (the editors are not consistent: e.g. "fast ganz zerstört" and "fast völlig zerstört" are one id).
Look the formula up there; if it is new, add an entry with its meaning and judgement before encoding it, and apply the
same id everywhere. `compile_draft.py` writes the ids used on a page into the header taxonomy, and `validate.py` refuses
an id that is not in the vocabulary, a free-text note inside the edition, and an uncategorised commentary row.

| On the page | Encode as |
|---|---|
| running head `Kap. N: title` | nothing; `<milestone unit="kephalaion" n="N"/>` from the Coptic numeral, `continues N` for the chapter in progress |
| `leer` | `vac.` → `<space/>` |
| a statement in the text block (`zerstört`, `abgerieben`, `unlesbar`, `nicht gelesen`, `geringe Spuren`, `verwischt` …), with or without a brace over several lines | `⁅=ID⁆` at its place, or `⁅=ID:line⁆` when it is all the line has, **one per line** → `<gap … ana="#ed.ID">`. Outside printed brackets the vocabulary's reason applies (abrasion and destruction = lost; smearing, illegibility, traces, not read = illegible); inside printed brackets the reason is lost |
| printed brackets without dots: `[ ]`, a bare `[` (never closed, nothing restored), `[?` | `[⁅=uncounted⁆]`, `[⁅=open-bracket⁆]`, `[⁅=open-bracket-query⁆]` |
| `[[x]]` with footnote `auspunktiert` | `⟦x⟧` → `<del rend="expunction">` + apparatus entry `expunged` |
| footnote `Lies ⟨x⟩y` / `Lies <word>` with letters missing | `⟨x⟩` → `<supplied reason="omitted">` + apparatus `correction` |
| `Dittographie` | `{x}` → `<surplus reason="repeated">` + apparatus `dittography` |
| `über der Zeile (nachgetragen)` | `\x/` → `<add place="above">` + apparatus `added-above` |
| `sinnlos`, `Schreibfehler`, `sic` with no correction | `«x»` → `<sic>` + apparatus `sic` |
| `[x?]` | `[x(?)]` → `@cert="low"` |
| every other footnote (`viell.`, `man erwartet`, `oder`, `so`, `unsicher`, `ganz zweifelhaft`, `Nicht`, `Spuren von`, `erg. nach`, `siehe`, `kein … Strich`, `Überschrift … statt`) and `Am unteren Rande eine Zeile` | `app LINE TYPE [printed=N] | lemma | reading ¦ reading | English note` → `<app loc ana="#app.TYPE"><lem/><rdg resp="#edition"/><note/></app>` in `<div type="apparatus">`; LINE by the margin numerals (or `header`, `bottom`) |
| the transcriber's own observations | `note N CATEGORY | English` with CATEGORY bracket · print · layout · reading · source → `<p n ana="#tr.CATEGORY">` |

## Analysis layers

`layers.py` writes `layers/pages/keph_pNNN.json` and corpus tables `lines`, `words`, `letters`, `strokes`, `gaps`,
`blanks`, `signs`, `corrections`, `notes`, `editorial` (every editors' statement in the text: id, meaning, reason,
whole line or in line) and `apparatus` (every footnote entry: type, lemma, readings, note) (`.csv`). Every row carries `page` and `line`. Letters carry `i` (index in
the line), `status` (certain · unclear · restored · omitted · surplus · added-above · expunged), `cert`, `word`, `stroke`,
`stroke_kind`, `diaeresis`, `large`, `sic`, `kephalaion`. Gaps, blanks and signs carry `before_letter`. Lines carry
`leiden`, `diplomatic` (what the manuscript shows: no spaces, `·` per lost or illegible letter), `reading` (all
letters incl. restorations, no diacritics, word spaces), `ekthesis`, `zone`, `type`, `kephalaion`.
The page JSON adds the page number, running title, kephalaia with title lines, and the margin numerals.

## Reporting

Say what was measured and what rests on your eye. Never claim 100 %. The usual residual risks are a single-letter
stroke or a diaeresis. List every editorial decision you made (wrong footnote numbering, printing anomalies kept as printed).
