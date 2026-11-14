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
| 049 | 15 → 16 | 35 | needs audit | 1e28143 | pilot page |
| 111 | 42 → 43 | 35 | needs audit | 1e28143 | pilot page |
| 159 | 65 | 33 | needs audit | 1e28143 | pilot page |
| 183 | 75 → 76 | 33 | needs audit | 1e28143 | pilot page |

Next unread page: **020**.

---

## 2. Open items

- Corrections to 018 and 019 are on branch `claude/optimistic-galileo-sykil7` (pushed, no PR yet).
- Audit 010–017 and the pilot pages (049, 111, 159, 183) with the strict method in §3.
- The p. 019 footnote on ⲥⲏⲣ is read in our note as "ⲥ̄ⲏ̄ⲣ̄ no overline"; confirm the footnote wording on the scan
  if p. 019 is touched again.

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
5. **`reconcile` is a check, not a target.** It only counts blobs whose top lies ≥ 2 px below the band centre,
   so it undercounts dots printed at line-centre height (all-dot lines) and it skips dots of area < 6. A
   remaining flag must be explained by one of those, verified by exact positions; otherwise the reading is wrong.
6. **Measure strokes on every line** (`measure.py strokes`), then crop each stroke at 4× and apply the
   ≥ half-a-letter rule by eye. Bars from the previous line's ϩ/ϣ/ϥ descenders show up as false strokes;
   curved strokes can be missed by the detector.
7. **Sublinear dots:** ϥ/ϩ/ⲣ dot sits left of the descender. A dotted ϣ has a separate dot in the lower bowl;
   compare with an undotted ϣ on the same page before accepting it.
8. **Final check:** `render_print.py` preview beside the scan, line for line, then `review_images.py`.

---

## 4. Encoding conventions decided so far

- Orphan `]` (opener not on the line, none at end of previous line): preceding dots illegible, `]` → `‡`, note.
- Cross-line bracket (`[` at end of line N, `]` on line N+1): close at the end of N if N has dots inside;
  reopen on N+1 as a lost gap; note on both lines. A bare `[` at the very end with nothing after → inline
  note `⁅opening bracket; the rest of the line is lost⁆`.
- Unclosed `[` followed by dots to the line end → close at the line end, note.
- Empty printed brackets (lost, extent not counted) → inline note, no gap.
- German: `leer` → `vac.`; `nicht gelesen`, `verwischt`, `abgerieben`, `geringe Spuren`, `einstweilen unlesbar`,
  `stark abgerieben`, `Rest abgerieben` → English inline note on the line(s) + note row; brace over several
  lines → one note per line ("See l. N"). Footnotes → English note rows ("apparatus").
- Parenthesised letters inside a restoration (e.g. [ⲟⲥ ⲁⲧ(ⲣ)ⲟⲩ]) → restoration without parentheses + note.
- Framed page number: bar above and below is the frame, not a stroke (note on l. 1). The tool always places
  its zone at the right, also on even pages where it is printed at the left.
- `ⲱ über der Zeile` (019 l. 29) → `\ⲱ/`.

---

## 5. Environment notes

- Python with the needed packages: `/usr/local/bin/python3.13` (plain `python` is 3.11 without lxml).
- Playwright's bundled Chromium build differs from the installed one: create a directory with symlinks
  `chromium-<expected>` and `chromium_headless_shell-<expected>` pointing at `/opt/pw-browsers/*-<installed>`
  and export `PLAYWRIGHT_BROWSERS_PATH` to it (expected build is printed by
  `python -c "from playwright.sync_api import sync_playwright as s; p=s().start(); print(p.chromium.executable_path)"`).
- Drive: search by exact file name; the folder has duplicates in a subfolder — use the copy whose parent is
  `1OIO3H2-nzmgHsSnNAEXyrDRmsL7BaEwi`. `download_file_content` results are too large for context and are saved
  to a tool-results file; decode the base64 `content` field from that file. Check 1553×2258.
- `gh` is restricted to search; open PRs with the GitHub MCP tool.

---

## 6. Session log

- **2026-11-13** — Routine run: read 015–019 (PR #3, merged). 018 and 019 later found to have many dot-count,
  dot-placement, stroke and letter errors (see §3).
- **2026-11-14** — Audited and corrected 019 (`67f95ca`) and 018 (`ea5025b`) on
  `claude/optimistic-galileo-sykil7`. Created this ledger.
