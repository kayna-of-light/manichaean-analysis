# Kephalaia reading — project ledger

Read this file in full at the start of every reading session. Update it at the end of every session
(page table, open items, lessons, session log) and commit it together with the pages.

Method: `.claude/skills/kephalaia-page-reading/SKILL.md`. Records: `data/kephalaia/epidoc/keph_pNNN.xml`,
review images `data/kephalaia/review/keph_pNNN.jpg`.

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
| 033 | 6 | 35 | read | 46373f3 | dotted ϣ l. 23; deletion point over ⲧ l. 12 → ⟦ⲧ⟧; corrections ⟨ⲛ⟩ ll. 15, 27 |
| 034 | 6 → 7 | 33 | read | 9ca08cb | kephalaion 7 opens l. 13, title ll. 14–15; "korrigiert; gemeint ist" l. 8 (see §2); point after ϣⲁⲁⲛⲏϩⲉ l. 12 in a note only |
| 049 | 15 → 16 | 35 | needs audit | 1e28143 | pilot page |
| 111 | 42 → 43 | 35 | needs audit | 1e28143 | pilot page |
| 159 | 65 | 33 | needs audit | 1e28143 | pilot page |
| 183 | 75 → 76 | 33 | needs audit | 1e28143 | pilot page |

Next unread page: **035**.

---

## 2. Open items

- Pages 020–024 (read and audited) are on branch `reading/2026-11-14`, PR #4. The editorial-vocabulary migration of
  all 19 pages builds on it (branch `claude/optimistic-galileo-iqh4x9`).
- The skill (`kephalaia-page-reading`) lists "a ϣ tail" as a known harmless reconcile flag. Taken as a rule that is wrong:
  see §3 item 7. The skill should be corrected (user's decision; routine runs may not edit it).
- Audit 010–017 and the pilot pages (049, 111, 159, 183) with the strict method in §3.
- The p. 019 footnote on ⲥⲏⲣ is read in our note as "ⲥ̄ⲏ̄ⲣ̄ no overline"; confirm the footnote wording on the scan
  if p. 019 is touched again.

---

- Vocabulary gaps met on 028–029 (routine runs may not edit the vocabulary): "vollständig zerstört" (28.24) was
  encoded with `destroyed` and a `source` note — consider an id `destroyed-completely`; "Kaum …" (29.13, "hardly")
  was encoded as `app.conjecture` with the doubt stated in the note — consider an id for rejected-but-mentioned
  restorations. 027 l. 1 prints an apostrophe after ⲧ; the draft markup has no sign for it (note only).
- `measure.py reconcile` crashes with a TypeError on any page that has an uncounted gap (`⁅=uncounted⁆`,
  `⁅=open-bracket⁆`, quantity None). On 026 and 029 it was run through a scratch wrapper that counts such gaps as 0
  (tool unchanged). The tool should treat `quantity` None as 0.
- Pages 025–029 (read 2026-11-14, second routine run) are on branch `reading/2026-11-14`; audit them with the strict method.
- Pages 030–034 (read 2026-11-14, third routine run) are on branch `reading/2026-11-14` (new PR); audit them with the strict method.
- Vocabulary gap met on 034 (routine runs may not edit the vocabulary): footnote 34.8 "ⲧⲉ̣ⲩ̈ⲉ̣ⲧⲏⲛⲉ korrigiert; gemeint ist ⲧⲟⲩⲓ̈ⲉⲧⲏⲛⲉ" (the manuscript corrects; the editors state the intended form) was encoded as
  `app.conjecture` with the wording in the note — consider an id for "korrigiert / gemeint ist". 33.22 "das erste ⲙ anscheinend
  getilgt" was encoded as `app.expunged` with the letter kept in the text (no double brackets printed) — consider an id for
  "apparently deleted" without `⟦ ⟧`.
- End-of-chapter punctuation without a dash: 30.11 prints a colon, 34.12 a single point after the last word. The draft markup
  has only `§` (:—), so both are in notes only; consider a sign for them.
- The page images sometimes show a small solid rectangle at a line end (31.28, 33.20) — a printing mark, not encoded.

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
5. **`reconcile` is a check, not a target.** It only counts blobs whose top lies ≥ 2 px below the band centre,
   so it undercounts dots printed at line-centre height (all-dot lines) and it skips dots of area < 6. A
   remaining flag must be explained by one of those, verified by exact positions; otherwise the reading is wrong.
6. **Measure strokes on every line** (`measure.py strokes`), then crop each stroke at 4× and apply the
   ≥ half-a-letter rule by eye. Bars from the previous line's ϩ/ϣ/ϥ descenders show up as false strokes;
   curved strokes can be missed by the detector.
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
10. **`strokes` percentages are not the extent.** The detector merges a stroke with neighbouring ink and also
   reports descenders of the line above. Print the pixel rows (grey < 130 / < 170) over the letter pair and read the
   bar's x-extent there; on 025 l. 4 the tool said ϩ 50 % but the pixel row gave 38 % (corrected before the PR).
11. **Footnote numbering:** check each footnote lemma against the line by the margin numerals (029: footnote "12"
   belongs to l. 13). Use `printed=N` on the app row.
12. **Final check:** `render_print.py` preview beside the scan, line for line, then `review_images.py`.

13. **Pixel-row check for every two-letter stroke.** The `strokes` percentages put a stroke over ⲙⲛ/ϩⲛ/ϩⲙ at ≥ 50 % on
   both letters more often than the pixel row does: on 030–034, 7 pairs fell below half on one letter by pixel row
   (30.1 ϩⲛ 43 %, 30.2 ϩⲙ 40 %, 31.26 ⲛϥ 46 %, 31.28 ⲙⲛ 47 %, 32.18 ⲗⲗ 16 %, 34.5/34.6 ⲙⲛ 47 %). Read the bar row (densest row of grey < 130 above the letters) and
   each letter's ink extent in the x-height band; encode on both letters only when each is ≥ 50 %.
14. **Lower-zone sheets for ϣ.** A sheet of the band y−12…y+14 of every line at 2.4–2.6× shows each ϣ's lower bowl well
   enough to pick out dotted ϣ (031 l. 8 and 033 l. 23 were seen this way and confirmed at 8× against an undotted ϣ). A blob scan
   of that band is too noisy (letter feet) to be useful.

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
- Large middle dot printed in the text (29.26 "ⲁⲧⲡⲉ • ⲉϥⲙⲟⲩⲣ") → `·` (g type middot) + layout note.
- Bracket printed after a letter with no opener (28.22 dots, 29.28 "ⲡ]") → `‡` after the dots/letter, note `bracket`;
  the letter before it is encoded as read.
- Unclosed `[` followed by letters and dots (28.31, 28.33) → the letters go into the restoration, closed at line end.
- `[x?]` inside a longer restoration (27.12 "[ⲥⲙⲟⲥ ⲉⲧⲧⲏⲧ? ⲡⲥⲁ]") → split into `[…(?)][…]`, note `bracket`.
- `[[x]]` with "auspunktiert" (15.16) is the scribe's deletion → `⟦x⟧` (del rend=expunction), not `{x}`.
- Parenthesised letters inside a restoration (e.g. [ⲟⲥ ⲁⲧ(ⲣ)ⲟⲩ]) → restoration without parentheses + note.
- Framed page number: bar above and below is the frame, not a stroke (note on l. 1). The tool always places
  its zone at the right, also on even pages where it is printed at the left.
- `ⲱ über der Zeile` (019 l. 29) → `\ⲱ/` + apparatus `added-above`.

- Editors' deletion point over a letter, explained in a footnote as "Tilgungspunkt" (33.12) → `⟦x⟧` + apparatus `expunged`,
  although no double brackets are printed; note `print` gives the dot position.
- Chapter-opening marginal numerals are attached to the line their glyph stands level with (34: l. 15), not to the line of
  their overline.

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
