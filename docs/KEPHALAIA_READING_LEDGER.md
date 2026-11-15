# Kephalaia reading — project ledger

Read this file in full at the start of every reading session. Update it at the end of every session
(page table, open items, lessons, decisions, session log) and commit it together with the pages.

Method: `.claude/skills/kephalaia-page-reading/SKILL.md`. Records: `data/kephalaia/epidoc/keph_pNNN.xml`,
review images `data/kephalaia/review/keph_pNNN.jpg`.

**How decisions are made.** This ledger has the final word: where it and the skill differ, the ledger wins. A session
that meets a case not covered here **decides it and writes the decision down** (§3 for method, §4 for encoding), with
the page and line where it first came up; it never leaves a "consider …" for someone else. The goal is stable results:
the same printed case is encoded the same way on every page. A session may also update the skill, the editorial
vocabulary and the reading tools when that makes the results more stable — in a separate commit, explained in the PR
and in §6. Already-read pages are changed only by an audit or by a decision that has to be applied retroactively, in
their own commit, listed in §6. §2 holds only work that is still to be done.

---

## 1. Page status

Status values: **read** (read once, verified by the routine's checks), **audited** (re-read line by line
with the strict method in §3 after the routine run), **needs audit** (read before the strict method; not
re-checked).

| Page | Kephalaion | Lines | Status | Last commit | Notes |
|---|---|---|---|---|---|
| 010 | 1 | 34 | needs audit | edcb5a5 | |
| 011 | 1 | 35 | needs audit | 20cc41a | |
| 012 | 1 | 34 | needs audit | 3374519 | |
| 013 | 1 | 35 | needs audit | e135be7 | heavy lacunae; cross-line bracket conventions first set here |
| 014 | 1 | 32 | needs audit | 8a4049d | |
| 015 | 1 | 34 | needs audit | 83a0746 | reconcile clean at the time; runs not segmented at brackets |
| 016 | 1 → 2 | 36 | needs audit | 0d3ef45 | kephalaion 2 opens l. 32, title ll. 33–34 |
| 017 | 2 | 35 | needs audit | 95e59f0 | |
| 018 | 2 | 37 | audited | ea5025b | ~95 % lacuna; corrected 2026-11-14 (runs, dots, l.13 stroke, ll.19/21/22 letters) |
| 019 | 2 | 35 | audited | 67f95ca | corrected 2026-11-14 (runs, dots, all strokes, ll.1/29 letters) |
| 020 | 2 | 35 | audited | 86b2dfa | read + audited 2026-11-14; audit added ϣ̣ l.32 |
| 021 | 2 | 36 | audited | e1dc18a | ll.5–11 no text (zerstört / unlesbar); audit added ϣ̣ l.23 |
| 022 | 2 | 35 | audited | 86cea54 | ll.1–8 no text; audit added ϣ̣ ll.28, 31 |
| 023 | 2 → 3 | 33 | audited | 52793b2 | kephalaion 3 opens l. 14, title ll. 15–16; audit added ϣ̣ ll.20, 22, 24 |
| 024 | 3 | 33 | audited | 8c518f2 | running title ⲙⲡⲥⲁϩ (apparatus); audit: no reading changes |
| 025 | 3 → 4 | 36 | read | aa56f9c | kephalaion 4 opens l. 7, title ll. 8–10; footnote correction ⟨ⲛ⟩ l. 26; l. 4 stroke corrected after pixel measure |
| 026 | 4 | 34 | read | 9cba172 | dotted ϣ ll. 3, 5; bare `[` l. 7; two `rejected` footnotes |
| 027 | 4 | 31 | read | d44719e | ll. 21–23 all dots; printed apostrophe after ⲧ l. 1 kept only in a note |
| 028 | 4 → 5 | 36 | read | c2f0e39 | kephalaion 5 opens l. 1, title ll. 2–3; l. 24 "vollständig zerstört" (see §2); correction ⟨ϭ⟩ l. 29 |
| 029 | 5 | 35 | read | 7609e62 | footnote "12" belongs to l. 13; "Kaum" footnote encoded as conjecture (see §2); \ⲡⲓⲑⲩ/ l. 30 |
| 030 | 5 → 6 | 36 | read | a15d578 | kephalaion 6 opens l. 12, title ll. 13–16; correction ⟨ⲙ⟩ l. 2; colon after ⲛⲁⲛⲏϩⲉ l. 11 in a note only |
| 031 | 6 | 33 | read | 993ad88 | dotted ϣ l. 8; «ⲡⲉⲓϣ» sic l. 7 ("unbekannt"); correction ⟨ⲡ⟩ l. 8 |
| 032 | 6 | 34 | read | 06bd1ea | bare `[` l. 23; «ϭⲓⲣⲁϥ ϭⲓⲣⲉ» sic l. 22; no dotted ϣ |
| 033 | 6 | 35 | read | 116d554 | dotted ϣ l. 23; deletion point over ⲧ l. 12 → ⟦ⲧ⟧; corrections ⟨ⲛ⟩ ll. 15, 27; l. 20 ⲉⲧϫⲏϥ corrected 2026-11-15 |
| 034 | 6 → 7 | 33 | read | 9ca08cb | kephalaion 7 opens l. 13, title ll. 14–15; "korrigiert; gemeint ist" l. 8 (see §2); point after ϣⲁⲁⲛⲏϩⲉ l. 12 in a note only |
| 035 | 7 | 34 | read | b12393c | nomen-sacrum overline printed over ⲡⲉ, not ⲓⲏⲥ (l. 13); unclosed `[` + dots + extant text l. 31 |
| 036 | 7 → 8 | 35 | read | b12393c | kephalaion 8 opens l. 27, title ll. 28–29; colon end of kephalaion 7 l. 26 (note only) |
| 037 | 8 → 9 | 36 | read | b12393c | kephalaion 9 opens l. 28, title ll. 29–30; correction ⟨ⲉ⟩ l. 17; 26 ⲉϥⲛⲁⲱⲡ fixed before commit (join) |
| 038 | 9 | 33 | read | 32b37be | \ⲛⲉ/ l. 9; correction ⟨ⲟⲩ⟩ l. 1; conjecture l. 32; ⲧⲙⲡⲥⲁⲙⲡⲓⲧⲛⲉ one word l. 32 |
| 039 | 9 | 34 | read | f2755ae | dotted ϣ ll. 26, 31; free-standing cross l. 19 (note only); «ⲁⲡⲛⲗⲁϩ» sic l. 5; ⟨ⲛ⟩ l. 7, ⟨ⲛⲏ⟩ l. 18; queried correction l. 24 |
| 040 | 9 | 34 | read | fdb64cd | middle dot l. 26; correction ⟨ⲙ⟩ l. 13; no dotted ϣ |
| 041 | 9 | 34 | read | 6a8b999 | dotted ϣ l. 13; \ⲛ/ l. 19, ⲛ\ⲉ/ l. 28; split bracket "[ blank ϣⲱ]" l. 31 |
| 042 | 9 → 10 | 35 | read | 67e8a8e | kephalaion 10 opens l. 24, title ll. 25–26; dotted ϣ l. 29; «ⲙⲙϣⲙϣⲉⲧⲉ» sic l. 4; stroke over ⲙⲛ covering neither by half l. 1 |
| 043 | 10 → 11 | 35 | read | 12d1ea7 | kephalaion 11 opens l. 22, title ll. 23–24; dotted ϣ l. 2; ⟨ⲡ⟩ l. 5, ⟨ⲓ⟩ l. 24; blank inside one restoration l. 34 |
| 044 | 11 → 12 | 35 | read | 529cb7e | kephalaion 12 opens l. 19, title ll. 20–22; l. 31 "unlesbar (abgerieben)" (new id); «ⲡⲁⲣⲁⲡⲉϩⲟⲩⲧ» sic l. 21; ⟨ⲉ⟩ l. 16 |
| 049 | 15 → 16 | 35 | needs audit | 1e28143 | pilot page |
| 111 | 42 → 43 | 35 | needs audit | 1e28143 | pilot page |
| 159 | 65 | 33 | needs audit | 1e28143 | pilot page |
| 183 | 75 → 76 | 33 | needs audit | 1e28143 | pilot page |

Next unread page: **045**.

---

## 2. Open items

- **Audits** with the strict method (§3): 010–017, the pilot pages 049, 111, 159, 183, and 025–044 (status "read").
  033 first: 33.20 had two letters the page does not print (ⲉⲧϩⲁⲥϫⲏϥ for ⲉⲧϫⲏϥ, found 2026-11-15). Every audit now
  includes `measure.py joins` and `spaces` (skill step 7a), which the pages before 035 never had.
- p. 019: our note reads the footnote on ⲥⲏⲣ as "ⲥ̄ⲏ̄ⲣ̄ no overline"; check the footnote wording on the scan during its next
  audit.

---

## 3. Method lessons (hard-won; apply every session)

**The image decides. Tools only propose.** Each tool sees one aspect; the answer comes from combining
measurement, several zoom levels and reading. Never change a reading to make a tool total come out.

What went wrong on 018/019 (2026-11-13) and must not happen again:
- Lacuna runs were padded to a whole-line blob total from `measure.py dots`. That total ignores bracket
  positions, so dots after a `[` were moved into the run before it, and sublinear dots were invented on
  letters that carry none (e.g. ⲉⲧⲁⲛⲓⲧ). Runs after a bracket were guessed as 3.
- Strokes were not measured at all on 019.
- Letters were misread at low zoom: ⲏⲡⲉ read as ⲛ̄ⲡⲉ; ϯ read as ⲧ; ϩ (reversed-S form) read as ⲥ or ⲧ;
  a ⲓ̣ dropped from ϣⲁⲩⲥⲙⲓⲛⲉ; a ϯ invented before ⲃⲣⲉ.

Strict method:
1. **Read every word at ≥ 4×.** 1.6–2.4× sheets are for orientation and counting only.
2. **Count every run separately, segmented at the printed brackets.** Get dot x-positions with
   `measure.py dots PAGE y0 y1 x0 x1` and bracket x-positions with `measure.py assign` (brackets show as glyphs
   about 6 px wide). Count dots between the bracket positions. Cross-check against the zoom by eye.
3. **Zoom halves overlap** (e.g. x 940–960): the same dot appears at the end of one strip and the start of the
   next. Convert strip pixels back to page x (x0 + px/scale) before adding counts.
4. **Faint dots exist** (area 4, e.g. p. 018 l. 10 x 609) and **specks exist** (blobs from the line above, the
   top hook of a bracket, German text). Every disputed blob gets a 6× zoom.
5. **`reconcile` is a check, not a target.** It only counts blobs of area ≥ 6 whose top lies ≥ 2 px below the zone
   centre. It therefore flags, without an error in the reading: dots of area < 6; dots at line-centre height (all-dot
   lines); a dot inside a letter's box (dotted ϣ, a dot joined to the letter, 30.13 ⲃ̣); a dotted letter inside a
   restoration (30.18 [ⲉ̣]); printed punctuation (30.11 colon, 34.12 point); "leer"; letter feet in title lines (34.15).
   Every remaining flag is explained by one of these with exact positions; otherwise the reading is wrong. Since
   2026-11-14 the tool counts uncounted gaps as 0 (it used to crash on them).
6. **Measure strokes on every line** (`measure.py strokes`), then crop each stroke at 4×. Bars from the previous
   line's ϩ/ϣ/ϥ descenders and the top serif of a bracket (31.27) show up as false strokes; curved strokes can be
   missed by the detector. The ≥ half-a-letter rule is decided on the pixel rows (item 10), not on the tool's %.
7. **Sublinear dots:** ϥ/ϩ/ⲣ dot sits left of the descender. A dotted ϣ has a separate dot in the lower bowl;
   compare with an undotted ϣ on the same page before accepting it. Look at every ϣ at 8×: the dotted ones show a
   small round dot sitting in the lower loop, apart from the stroke; the tail of ϣ is a curve joined to the letter.
   On 020–023 six real dots were first written off as "the tail of ϣ" because a tool flag was taken as the answer
   instead of looking (2026-11-14). A blob scan (small components inside a letter's box) can point to places worth
   a look, but it neither proves nor rules out a dot — the decision is made on the zoom.
8. **Audit sheet:** 4× strips of five lines in three overlapping x-ranges (370/440–780, 760–1100, 1080–1430);
   compare each against the draft rows printed alongside.
9. **German statements:** look each formula up in the vocabulary and encode its id; never paraphrase it in a note.
   Check where printed brackets stand around a statement (a bare `[` at the line start is a separate loss).
10. **`strokes` percentages are not the extent.** The detector merges a stroke with neighbouring ink. For every
   stroke over two letters, take the bar's x-extent on its densest pixel row (grey < 130, a few rows above the
   letters) and each letter's ink extent in the x-height band; the stroke goes on a letter only if it covers ≥ 50 % of
   it. Examples where the tool said both and the pixel row said one: 25.4 ϩ 38 %; 30.1 ϩⲛ (ϩ 43 %), 30.2 ϩⲙ (40 %),
   31.26 ⲛϥ (46 %), 31.28 ⲙⲛ (47 %), 32.18 ⲗⲗ (16 %), 34.5 and 34.6 ⲙⲛ (47 %). State the measured % in a `print` note.
11. **Footnote numbering:** check each footnote lemma against the line by the margin numerals (029: footnote "12"
   belongs to l. 13). Use `printed=N` on the app row.
12. **Final check:** `render_print.py` preview beside the scan, line for line, then `review_images.py`.
13. **Lower-zone sheets for ϣ.** A sheet of the band y−12…y+14 of every line at 2.4–2.6× shows each ϣ's lower bowl
   well enough to pick out dotted ϣ (31.8 and 33.23 were found this way and confirmed at 8× against an undotted ϣ).
   A blob scan of that band is too noisy (letter feet) to be useful.
14. **Strip joins (2026-11-15).** The left and right 4× halves overlap at x 940–960; a letter at the edge is easily
   written twice or one invented: 037.26 ⲉϥⲛⲁⲱⲱⲡ for ⲉϥⲛⲁⲱⲡ, 038.4 a ϯ before ⲡⲁϫⲉϥ that is the ⲡ itself. Both were
   caught only on the print preview / a join strip. Run `measure.py joins NNN` and compare every line before compiling.
15. **Word division (2026-11-15).** 038.32 ⲧⲙ̄ⲡⲥⲁⲙⲡⲓⲧⲛⲉ had been split into two words by eye. `measure.py spaces NNN`
   compares blank runs with the reading; every difference is explained (enlarged-letter legs, dot runs, unmarked blank,
   bracket-narrowed space, margin numerals) or the reading is corrected.
16. **Measure blank widths (2026-11-15).** Estimated widths of unmarked blanks were wrong by up to 120 px (035.13: 165
   written, 43 measured). Take the width from the x-height band (`spaces` prints it) and an ordinary 20 px space before an
   enlarged letter is no `%` (039.34).
17. **A stroke over two letters that covers neither by half (2026-11-15, 42.1).** The ≥ 50 % rule assumes the bar lies
   mostly over one letter. When the bar is centred on the join and covers both letters below 50 % (42.1 ⲙⲛ: 47 % / 46 %),
   it is encoded on both, so that a printed stroke is never dropped; the measured % goes in the `print` note.
18. **Dots that a tool does not see (2026-11-15).** A sublinear dot joined to the foot of ⲓ (the "!" shape, 43.17, 44.2) or
   of ϩ (44.22) is a real dot: encode the letter as dotted and say in the note that reconcile misses it. The dot of ⲣ is
   sometimes printed right of the descender, at its foot (41.11, 41.20, 42.5); it belongs to the ⲣ. Decide both on an
   8–10× zoom.
19. **Footnotes are read in full before the notes are written (2026-11-15).** On 041–044 every page had a footnote that
   changed the text (added-above letters, corrections, sic); read the footnote block at 2× together with the last lines.

---

## 4. Encoding conventions decided so far

- Orphan `]` (opener not on the line, none at end of previous line): preceding dots illegible, `]` → `‡`, note.
- Cross-line bracket (`[` at end of line N, `]` on line N+1): close at the end of N if N has dots inside;
  reopen on N+1 as a lost gap; note (category `bracket`) on both lines.
- Unclosed `[` followed by dots to the line end → close at the line end, note (`bracket`).
- **Editors' German (since 2026-11-14): structure, not prose.** Every formula is looked up in
  `data/kephalaia/editorial_vocabulary.json` (new formula → add an entry with meaning and judgement first).
  In the text: `⁅=ID⁆` / `⁅=ID:line⁆`, one per line even under a brace → `<gap … ana="#ed.ID">`. Bare `[` →
  `[⁅=open-bracket⁆]`, `[ ]` → `[⁅=uncounted⁆]`, `[?` → `[⁅=open-bracket-query⁆]`. Footnotes → `app` rows
  (`<listApp>`), typed by the vocabulary. Commentary rows carry a category (bracket · print · layout · reading · source).
  `validate.py` refuses free-text inline notes, unknown ids and uncategorised commentary.
- Judgements fixed in the vocabulary: abrasion or destruction named → lost; smearing, illegible, traces, not read →
  illegible; inside printed brackets → lost (the bracket wins over the word, e.g. 21.4 traces in brackets).
  A bare `[` at a line start beside a braced statement (21.8–11) = lost beginning + the statement for the rest.
- Large middle dot printed in the text (29.26 "ⲁⲧⲡⲉ • ⲉϥⲙⲟⲩⲣ") → `·` (g type middot) + layout note (see §7).
- Bracket printed after a letter with no opener (28.22 dots, 29.28 "ⲡ]") → `‡` after the dots/letter, note `bracket`;
  the letter before it is encoded as read.
- Unclosed `[` followed by letters and dots (28.31, 28.33) → the letters go into the restoration, closed at line end.
- `[x?]` inside a longer restoration (27.12 "[ⲥⲙⲟⲥ ⲉⲧⲧⲏⲧ? ⲡⲥⲁ]") → split into `[…(?)][…]`, note `bracket`.
- `[[x]]` with "auspunktiert" (15.16) is the scribe's deletion → `⟦x⟧` (del rend=expunction), not `{x}`.
- Parenthesised letters inside a restoration (e.g. [ⲟⲥ ⲁⲧ(ⲣ)ⲟⲩ]) → restoration without parentheses + note.
- Framed page number: bar above and below is the frame, not a stroke (note on l. 1). The tool always places
  its zone at the right, also on even pages where it is printed at the left.
- `ⲱ über der Zeile` (019 l. 29) → `\ⲱ/` + apparatus `added-above`.

- Deletion point named in a footnote ("Tilgungspunkt", 33.12) → `⟦x⟧` + apparatus `expunged`, although no double
  brackets are printed; a `print` note gives the dot's position. "anscheinend getilgt" (33.22) → the letter stays as
  printed; apparatus `expunged` only, the doubt in the note.
- Footnote formulas decided 2026-11-14 (now in the vocabulary as German variants of existing ids, so no page changes):
  "vollständig zerstört" (28.24) → `destroyed`; "Kaum …" (29.13) and "korrigiert; gemeint ist …" (34.8) →
  `app.conjecture` with the wording and its strength in the note.
- **Every printed mark that is not a letter is encoded where it stands as a sign** (decided 2026-11-15, replacing the
  earlier "note only" rule): colon `⁚` (30.11, 36.26), point `∙` (34.12), apostrophe `ʼ` (27.1), cross `†` (39.19),
  block `▪` (31.28, 33.20), large middle dot `·` (29.26). Spacing as printed (a colon closer than a word space is written
  without a space). A shape that fits none of these gets a new type in `model.SIGNS` and `decompile.SIGNS` and a row in
  §7 — never a note only, so that `signs.py` finds every occurrence. The note keeps the position and measurements.
  Reconcile may flag a sign below line centre; that is expected.
- Unclosed `[` followed by a dot run and then extant text (letters with their own sublinear dots, or the line's ordinary
  text; 35.31, 39.32) → the gap is closed after the last dot, note `bracket`. (Contrast 28.31/28.33, where the letters
  after the bracket are restorations.)
- A nomen-sacrum overline printed displaced onto the preceding word (35.13: bar over ⲡⲉ, ⲓⲏⲥ bare) is encoded as printed,
  with a `print` note giving the measured extent.
- A free-standing printed cross (39.19: equal arms, 23 px wide against 17 px for ϯ, after a 64 px blank at the line end)
  is a sign, not the letter ϯ: not encoded in the text; `layout` note with its position.
- Footnote formulas decided 2026-11-15 (vocabulary variants, ids unchanged): "x sic für y" (39.5) → «x» in the text +
  `app.sic` with y as reading; "x sic, lies y" (39.7) → `app.correction`, the correction in the text, "sic" in the note;
  "lies …? oder …?" with a question mark (39.24) → `app.conjecture`, nothing changed in the text, every form a reading.
- "leer" inside a line (39.7, 39.24) → `vac.` at its place, like "leer" at a line end.
- Chapter-opening marginal numerals are attached to the line their glyph stands level with (34.15), or, when they stand
  between two lines, to the upper one (30.14).
- Decided 2026-11-15 (pages 040–044):
  - The framed page number printed inside restoration brackets ([ⲙⲅ] 43, [ⲙⲇ] 44) is encoded as a restoration without
    strokes; the bars are the frame.
  - One printed bracket pair that holds more than the encoder can express in one restoration is split, with a `bracket`
    note: an empty stretch followed by restored letters "[ blank ϣⲱ]" (41.31) → `[⁅=uncounted⁆][ϣⲱ]`; restored letters
    followed by an empty stretch "[ⲣⲱⲙⲉ blank]" (43.35) → `[ⲣⲱⲙⲉ ⁅=uncounted⁆]`; an unmarked blank inside one restoration
    (43.34) → `[ⲓ̈ⲧ] % [ⲧⲁⲣⲭⲏ …]`.
  - An unclosed `[` with restored letters followed by an editors' statement (44.5 "ⲧ[ⲛⲁϭ Rest zerstört") → the restoration
    and the statement both inside the bracket, closed at the line end; the bracket makes the reason lost.
  - A footnote correction whose supplied letter carries a diaeresis the printed letters lack (43.24 "Lies ϣⲃⲓ̈ⲁ⟨ⲓ̈⟩ⲧ") → the
    supplied letter takes the footnote's form, the printed letters stay as printed; the difference goes in the app note.
  - A footnote that confirms a reading and calls it unintelligible ("scheint so dazustehen (unverständlich)", 44.21) is a
    `sic`: «x» around the lemma letters only, even inside a longer word (ⲙⲙⲛ̄ⲧ«ⲡⲁⲣⲁⲡⲉϩⲟⲩⲧ»).
  - Vocabulary variants added (ids unchanged): "klein über der Zeile" and "anscheinend über der Zeile" → `added-above`;
    "für … ist der Raum zu knapp" and "Die Spuren passen nicht zu" → `rejected`; "sic mit …" and "scheint so dazustehen
    (unverständlich)" → `sic`; "Rest zerstört" → `destroyed`. New id `illegible-abraded` for "unlesbar (abgerieben)"
    (44.31): abrasion named, so lost.


---

## 5. Environment notes

- Python with the needed packages: `/usr/local/bin/python3.13` (plain `python` is 3.11 without lxml). Alternative
  used on 2026-11-14: `python -m pip install lxml numpy scipy pillow playwright==1.63.0` for 3.11 — 1.63.0 matches
  the preinstalled `/opt/pw-browsers` Chromium build (1243), so no symlinks are needed.
- Playwright's bundled Chromium build differs from the installed one: create a directory with symlinks
  `chromium-<expected>` and `chromium_headless_shell-<expected>` pointing at `/opt/pw-browsers/*-<installed>`
  and export `PLAYWRIGHT_BROWSERS_PATH` to it (expected build is printed by
  `python -c "from playwright.sync_api import sync_playwright as s; p=s().start(); print(p.chromium.executable_path)"`).
- Drive: search by exact file name; the folder has duplicates in a subfolder — use the copy whose parent is
  `1OIO3H2-nzmgHsSnNAEXyrDRmsL7BaEwi`. `download_file_content` results are too large for context and are saved
  to a tool-results file; decode the base64 `content` field from that file. Check 1553×2258.
- `gh` is restricted to search; open PRs with the GitHub MCP tool.
- 2026-11-15 (second run): the worker process restarted in the middle of p. 044; drafts, images, scratch scripts and
  installed packages survived, and work went on from the draft. Write each line to the draft right after viewing it, so a
  restart loses nothing.
- Pillow: if `from PIL import Image` fails with "cannot import name '_imaging'", the Debian copy in
  /usr/lib/python3/dist-packages is shadowing pip's; `python -m pip install --ignore-installed pillow` fixes it (2026-11-14).

---

## 6. Session log

- **2026-11-13** — Routine run: read 015–019 (PR #3, merged). 018 and 019 later found to have many dot-count,
  dot-placement, stroke and letter errors (see §3).
- **2026-11-14** — Audited and corrected 019 (`67f95ca`) and 018 (`ea5025b`) on
  `claude/optimistic-galileo-sykil7`. Created this ledger.
- **2026-11-14** — Routine run: read 020–024 (PR #4). Same day, after the ledger was introduced, re-read all five
  pages line by line at 4× (three overlapping strips per line). Letters, gap counts and strokes held; six dotted ϣ
  had been dismissed as ϣ tails and were corrected (020 l.32, 021 l.23, 022 ll.28/31, 023 ll.20/22/24). German
  brace notes now carry one note row per line. All five pages marked audited.
- **2026-11-14** — Editorial layer: built `data/kephalaia/editorial_vocabulary.json` (German formula → id, meaning,
  judgement), `decompile.py` (TEI → draft, exact round trip on all 19 pages), gap tokens `⁅=ID⁆`, apparatus rows,
  commentary categories, `⟦ ⟧`, and `editorial` / `apparatus` layer tables. Migrated all 19 pages from the page images'
  footnotes: 139 statements, 46 apparatus entries; 88 free-text inline notes and the brace/"See l." rows removed.
  Two encoding errors fixed on the way: 15.16 expunction (was surplus), 19.7 uncounted loss inside brackets (was
  missing).
- **2026-11-14** — Routine run (second): read 025–029 on `reading/2026-11-14`. All five validate "ok"; reconcile flags
  explained by dots at line-centre height or of area < 6 (positions in the page notes). Problems: `reconcile` crashes
  on uncounted gaps (wrapper used, see §2); `measure.py` strokes overstates coverage when a bar touches the line above
  — 025 l. 4 corrected by pixel measure in a separate commit (`aa56f9c`). Dotted ϣ accepted after zoom: 026 ll. 3, 5;
  027 l. 9; 028 ll. 12, 23, 29; 029 l. 28. No pages skipped; images downloaded from Drive (1553×2258).
- **2026-11-14** — Routine run (third): read 030–034 on `reading/2026-11-14` (branched from main after PR #6). All five
  validate "ok". Reconcile flags explained: dots of area < 6 (031 l. 33, 034 l. 4), a dot inside a letter's box (030 l. 13 ⲃ̣,
  031 l. 8 dotted ϣ), restored dotted letters (030 l. 18 [ⲉ̣]), printed punctuation (030 l. 11 colon, 034 l. 12 point) and letter
  feet below the zone centre in a title line (034 l. 15). `reconcile` still crashes on uncounted gaps (032); run through the
  same scratch wrapper (quantity None → 0). Dotted ϣ accepted after 8× comparison: 031 l. 8, 033 l. 23. Images downloaded from
  Drive (1553×2258). Environment: Pillow had to be reinstalled with `pip install --ignore-installed pillow` (the Debian copy in
  /usr/lib/python3/dist-packages shadowed it and failed to import `_imaging`). No pages skipped.
- **2026-11-14** — Governance cleanup (with the user): the ledger decides and records decisions instead of leaving
  suggestions. §2 emptied of "consider …" items; their decisions moved to §3/§4. `measure.py reconcile` fixed (uncounted
  gaps count as 0; output on 032 identical to the scratch wrapper). Vocabulary: German variants added to `destroyed`,
  `app.conjecture`, `app.expunged` (ids unchanged; all 29 pages validate "ok"). Skill: ledger precedence, pixel-row
  stroke rule, dotted-ϣ sheet, reconcile flag list (the "ϣ tail" excuse removed).
- **2026-11-15** — Routine run: read 035–039 on `reading/2026-11-15`. All five validate "ok". Reconcile flags explained:
  a fragment of "leer" (035.24), cut marginal numerals in title lines (036.28, 037.29), a dot below the zone (037.14), a
  dot joined to ϥ (038.23), a dot of area 3 (039.32). Dotted ϣ accepted after 8× comparison: 039 ll. 26, 31; none on
  035–038. Errors caught before commit by the print preview and new checks: 037.26 doubled letter at the strip join,
  038.4 invented ϯ at the strip join, 038.32 false word division; 035–037 blank-width notes corrected to measured values
  in a separate commit (`b12393c`, notes only). Tool: `measure.py spaces` and `joins` (`4f320c5`); skill step 7a
  (`9a66f59`); vocabulary: "sic für", "sic, lies", "lies …?" (ids unchanged). All 33 pages re-validated "ok" after each
  change. Images downloaded from Drive (1553×2258); Pillow again needed `--ignore-installed`. No pages skipped.
- **2026-11-15** — With the user, after PR #8: printed signs that were in notes only (apostrophe 27.1, colons 30.11/36.26,
  blocks 31.28/33.20, point 34.12, cross 39.19) are now encoded as `<g>` signs (`b5dbb19` tool, `bd28e3f` pages; no
  letter changes) and listed by `signs.py`; new §7 register with open questions; the user's observation that the Coptic
  was drawn by hand with templates is recorded there. `decompile.py` fix (`f0787af`): "[x(?)][y]" (27.12) had been
  merged into one restoration; decompile → compile is now identical on all 34 pages. While measuring 33.20 a reading
  error was found and corrected (`116d554`): ⲉⲧϫⲏϥ, not ⲉⲧϩⲁⲥϫⲏϥ; 033 moves to the front of the audit queue (§2).
  Images 027, 030, 031, 033, 034 downloaded from Drive (1553×2258). All pages validate "ok".
- **2026-11-15** — Routine run (second): read 040–044 on `reading/2026-11-15`. All five validate "ok"; all 39 pages
  re-validated after each vocabulary change. Reconcile flags explained: dots at line-centre height (042.12–18, 043.21,
  044.15/29/30/32/34), dots of area < 6 (042.3, 043.18), dots joined to ⲓ or ϩ (043.17, 044.22), dots at the foot of the
  zone (041.14/30, 043.1/23), margin and line numerals (042.25, 043.23, 044.12/19), German umlauts (044.5). Dotted ϣ
  accepted after 8–10× comparison: 041.13, 042.29, 043.2; none on 040, 044. Caught before commit: 040.10 a dot written
  under ⲉ that belongs to ⲥ (14×); 043 page number had been given strokes (frame bars; fixed in `12d1ea7`). Vocabulary:
  six German variants and one new id (`illegible-abraded`), each in its own commit (`da8be69`, `d07f18b`, `9775ee6`,
  `d6ba4f4`, `c01ac36`, `c237d59`). Method: §3 items 17–19; encoding decisions in §4 (2026-11-15). Images downloaded from
  Drive (1553×2258). No pages skipped. The worker restarted once during 044 (see §5).


---

## 7. Signs and patterns to study

Marks the reading encodes but does not yet understand. The aim is to collect occurrences until a pattern shows; do not
guess a meaning before then. `python signs.py` lists every occurrence (page.line, neighbouring words, line end, end of
kephalaion, preceding blank). After each session, update the counts below and write down any pattern the list now
shows, with the occurrences that support it.

| Type | Draft | Occurrences (2026-11-15) | What the occurrences show so far |
|---|---|---|---|
| middot | `·` | 10.34, 29.26, 32.9, 40.26, 159.33 | mid-line between words (4×; 40.26 a large round dot, area 44, between ⲛⲧⲉϥⲉⲕⲕⲗⲏⲥⲓⲁ and ⲛϣⲁⲣⲡ); once at a line and kephalaion end (159.33) |
| colon | `⁚` | 30.11, 36.26 | both at the end of a kephalaion, after the last word, no dash (contrast the end mark `:—`) |
| point | `∙` | 34.12 | end of a kephalaion, after a word space |
| block | `▪` | 31.28, 33.20 | line end, mid-kephalaion; may be a printing mark, not the manuscript's |
| cross | `†` | 39.19 | line end after a 64 px blank, mid-kephalaion (9) |
| apostrophe | `ʼ` | 27.1 | after ⲧ at the start of a line |

Kephalaia 9, 10 and 11 end on 042.23, 043.21 and 044.18 with no printed end sign (two of the three end lines are
damaged), so far the colon/point at a chapter end is the exception, not the rule (30.11, 34.12, 36.26 against 042–044).

Open questions: Are colon and point two forms of one chapter-end sign? Does the cross recur at section breaks? Are the
blocks the printer's or the editors'? Do the middle dots separate units of sense?

**About the printed Coptic (user observation, 2026-11-15).** The Coptic of this edition appears to be hand-drawn with
letter templates (stencils), not set in metal type. This explains why overlines vary in length and position (35.13 bar
displaced onto ⲡⲉ; strokes near the 50 % mark on ⲙⲛ, ϩⲛ, ⲛⲛ) and why some strokes and dots look blurred. Decision:
the ≥ 50 % rule stays, because it keeps the encoding the same on every page, and every measured percentage stays in
the `print` notes so that the borderline cases (45–55 %) can be re-judged together later. Shapes that vary between
copies of one letter (ϯ 17 px wide, the 39.19 cross 23 px) are compared on the same page.
