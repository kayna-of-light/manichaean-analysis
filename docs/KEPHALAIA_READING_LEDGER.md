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
| 045 | 12 → 13 | 33 | read | d8dae6f | kephalaion 13 opens l. 16, title ll. 17–18; ll. 20–24 "bis auf geringe Spuren zerstört" (new id); unpaired `]` ll. 9, 10, 13; rejected footnote l. 28 |
| 046 | 13 → 14 | 33 | read | c35d7c0 | kephalaion 14 opens l. 13, title ll. 14–15; ll. 21–24 "bis auf ganz geringe Spuren zerstört" (new id); dotted ϣ l. 16; very faint dots ll. 1–12 |
| 047 | 14 → 15 | 35 | read | e1d2c42 | kephalaion 15 opens l. 22, title ll. 23–25; l. 6 "nur geringe Spuren"; ll. 34–35 "nicht gelesen"; stroke touching ⲃ l. 31 |
| 048 | 15 | 35 | read | 7e6a64b | \ⲡⲙⲟⲩ/ l. 20 (footnote "über der Zeile"); l. 30 "unlesbar" + unpaired `]`; ll. 11, 22, 23 dots below the ink threshold |
| 049 | 15 → 16 | 35 | needs audit | 1e28143 | pilot page |
| 050 | 16 | 33 | read | 2b06aa0 | correction ⟨ⲓ⟩ l. 25; dotted ϣ l. 25; two ⲡⲛⲁ bars beginning on the second ⲡ (ll. 23, 26) |
| 051 | 16 | 33 | read | 58b6428 | dittography over ll. 30–31 (split per line); "auf Rasur" l. 10, "klein" l. 14 (new ids); ⟨ⲙ⟩ l. 26; dotted ϣ l. 9 |
| 052 | 16 | 34 | read | e81b90d | middle dots ll. 12, 19; apostrophe l. 20; \ⲁⲃⲁⲗ/ l. 16 ("oberhalb der Zeile"); dotted ϣ l. 12 |
| 053 | 16 | 32 | read | aa81b5b | \ϥ/ l. 5; "von …, vielleicht" l. 21; "ganz unsicher" l. 24; dotted ϣ ll. 8, 29 |
| 054 | 16 | 32 | read | 7e481da | raised mark after ϩ l. 10 → apostrophe; two bars over ⲙⲛⲛ l. 20; ⟨ⲛ⟩ l. 25; ⲯ l. 14; dotted ϣ l. 27 |
| 055 | 16 → 17 | 34 | read | 1f9e96f | kephalaion 17 opens l. 16, title ll. 17–18; pale print (strokes at grey < 170); enlarged dotted ⲡ l. 19; l. 34 all dots |
| 056 | 17 | 34 | read | 476cd88 | dotted ϣ l. 5 (found by reconcile); "abgerieben" l. 10; enlarged ⲡ̣ l. 7, ⲧ̣ l. 30; ⲛϩ ⲙⲛ l. 23 ⲙ 48 % |
| 057 | 17 | 32 | read | 8fd621d | dotted ϣ l. 25; ⟨ⲥ⟩ l. 3, ⟨ⲡⲁ⟩ l. 22; unnumbered footnote assigned to l. 11 by content; "[ blank ϣⲁⲙ]ⲧ" l. 32 |
| 058 | 17 → 18 | 33 | read | cc84f9c | kephalaion 18 opens l. 1, title ll. 2–3; footnotes numbered one line low (printed=N); new sign high-point l. 29; "fraglich" l. 23; dotted ϣ ll. 2, 5, 7, 30 |
| 059 | 18 | 33 | read | 20a40a3 | l. 1 all dots (not in `bands`); ⟨ⲡⲁ⟩ l. 3, ϣⲟⲩϣⲟ⟨ⲩ⟩ l. 9; orphan ] after ⲧ l. 25; no dotted ϣ |
| 060 | 18 → 19 | 32 | read | a1d97a1 | kephalaion 19 opens l. 13, title ll. 14–15; ll. 2–12 left half lost (orphan ]); \ϩ/ l. 27; "oder" footnote assigned to l. 30 |
| 061 | 19 | 31 | read | 56311b3 | ll. 1, 12 all dots; nomen-sacrum bars over ⲏⲥ only (ll. 17, 27); ⟨ⲡ⟩ l. 23; middot l. 20; no dotted ϣ |
| 062 | 19 | 33 | read | 99361c8 | pale page, left half abraded (footnote → `app.page-condition`); new sign loop-mark l. 27; ll. 29–33 "geringe Spuren"; dotted ϣ ll. 23, 26 |
| 063 | 19 → 20 | 35 | read | d78fbde | kephalaion 20 opens l. 19, title ll. 20–21; dotted ϣ l. 17; middot l. 25; ll. 1–18 heavy lacunae |
| 064 | 20 → 21 | 35 | read | 9975070 | end mark `:—` mid-kephalaion l. 1; kephalaion 21 opens l. 13, title ll. 14–16; "[ wohl leer ]" l. 32 (new id); ⟨ⲟⲩ⟩ l. 21; "wie im Boh." l. 22 |
| 065 | 21 → 22 | 33 | read | ba24deb | kephalaion 22 opens l. 14, title ll. 15–16; ll. 19–20, 24, 32–33 statements; ⟨ⲱ⟩ l. 18; l. 31 run corrected after reconcile |
| 066 | 22 → 23 | 36 | read | d0cda57 | kephalaion 23 opens l. 28, title ll. 29–30; ll. 20–21 "fast ganz zerstört"; arched stroke over ϥ l. 8; no dotted ϣ |
| 067 | 23 | 34 | read | 27455f0 | dotted ϣ ll. 5, 29; unmarked blanks ll. 18 (76 px), 20 (41 px); enlarged Ⲁ restored in brackets l. 23; orphan ] l. 27 |
| 068 | 23 | 33 | read | f9148cd | ll. 1–15 left part lost (orphan ]); block in a dot row l. 4; double ] l. 6; "Qual. zu" (new id `app.grammar`) l. 25; conjecture l. 26 |
| 069 | 23 | 33 | read | 13eb446 | dotted ϣ l. 17; ⟨ⲧⲉ⟩ l. 14; [ⲛⲁϭ?] l. 14; 29 ⲛⲉⲙⲉⲩ fixed before commit (join) |
| 070 | 23 → 24 | 33 | read | ce51577 | kephalaion 24 opens l. 8 (numeral), l. 9 blank, title ll. 10–11; dotted ϣ l. 28; ⟨ⲱⲅ⟩ l. 29; oblique stroke on ⲗ ll. 19, 24, 26; enlarged Ⲛ at line end l. 14 |
| 071 | 24 | 33 | read | afb6169 | ⟨ⲛ⟩ l. 16; \ⲙ/ l. 30 ("üb. d. Zeile"); enlarged Ⲛ̄ at a line end after % l. 14; middot l. 9; "[ⲟⲩⲱϣⲉ ?ⲟⲩⲁ]" split l. 21; no dotted ϣ |
| 072 | 24 | 35 | read | cdac82b | ll. 9–17 heavy lacunae; ⟨ϩ⟩ + "Qual. von" l. 29; two separate bars over ⲣⲣ l. 14; ‡ ll. 2, 3, 23; no dotted ϣ |
| 073 | 24 | 33 | read | edad638 | block ▪ at a line start l. 3; ll. 12–13 all dots; "Lies" removing printed letters ll. 18, 29 (text as printed); dotted ϣ l. 22; 24 ⲥⲉϩⲱⲩ fixed before commit (preview) |
| 074 | 24 | 33 | read | 24a871f | dotted ϣ l. 3; ⟨ⲥ⟩ l. 20; "ganz unsicher" l. 32; [ⲉ(ⲉ)ϥ] l. 27; 29 a dot under ⲣ removed before commit (reconcile) |
| 075 | 24 | 34 | read | 61f0b1c | "Über dem ⲉ noch ein ⲛ" l. 9 (text unchanged); block ▪ in a dot row l. 8; dotted ϣ ll. 29, 30; five sections opening with enlarged Ⲡ (ll. 13, 16, 20, 24, 32) |
| 076 | 24 → 25 → 26 | 36 | read | b203328 | kephalaion 25 opens l. 15, title ll. 16–17 "Überschrift ganz verwischt" (new id); kephalaion 26 opens l. 26, title ll. 27–28; apostrophe inside a dot run l. 9; «ϯⲙⲏⲧⲉ» sic l. 9; no dotted ϣ |
| 077 | 26 → 27 | 34 | read | c2fcccc | kephalaion 27 opens l. 22, title ll. 23–24; dotted ϣ l. 21; small middle dot l. 31; correction removing ⲛ l. 9 (text as printed) |
| 078 | 27 | 34 | read | 9ab495d | dotted ϣ l. 3; ⟨ⲛ⟩ l. 15; oblique stroke over ⲡ l. 33; "oder … zu erg." l. 4; correction removing ⲡ l. 21 |
| 079 | 27 → 28 | 35 | read | 9f20aca | kephalaion 28 opens l. 13, title ll. 14–15; dotted ϣ ll. 8, 19, 23, 28 (two); "(?)" after a word l. 1; no footnotes |
| 080 | 28 | 36 | read | 8dfdbc5 | l. 13 all dots (not in `bands`); dotted enlarged Ⲡ ll. 5, 25; two bars over ⲛⲓⲏⲥ l. 22; ⟨ⲛ⟩ l. 18; ⲡⲁⲏⲣ l. 30 fixed before commit (strip join); dotted ϣ l. 10 |
| 081 | 28 → 29 | 33 | read | aaa03d8 | kephalaion 29 opens l. 21, title ll. 22–23; "Lies … oder …" l. 24 (conjecture, new variant); oblique stroke over ϥ l. 15; no dotted ϣ |
| 082 | 29 | 34 | read | 297d0c0 | the nine thrones; orphan ] l. 13; oblique tick over ⲁ l. 12; two bars over ⲛⲓⲏⲥ l. 33; "zwischen den Zeilen" l. 25 (added-above, new variant); no dotted ϣ |
| 083 | 29 → 30 | 33 | read | 826570e | kephalaion 30 opens l. 17, title l. 18; unmarked blanks ll. 1, 4, 8; block ▪ l. 5; ⟨app⟩ "Lies ⲛ̄ⲣⲣⲟ" l. 3 (text as printed); dotted ϣ l. 28 |
| 084 | 30 → 31 | 34 | read | 8ff9aed | kephalaion 31 opens l. 5, title ll. 6–8; \ⲟⲩ/ l. 4; double opening bracket l. 17; enlarged Ⲛ̄ at the line end l. 9; ⲯ (not ϯ) in ⲧⲯⲩⲭⲏ; no dotted ϣ |
| 085 | 31 → 32 | 35 | read | 371acbf | kephalaion 32 opens l. 19, title ll. 20–21; ⟨ⲩ⟩ l. 17; \ⲡ/ l. 8; l. 35 a turned-over word (ⲙ̄ⲡⲣⲓⲉ); dotted ϣ ll. 16, 22, 33 |
| 086 | 32 → 33 → 34 | 35 | read | ccdff96 | kephalaion 33 opens l. 18, title ll. 19–21; 34 opens l. 31, title ll. 32–33; ⟨ⲛ⟩ l. 12, ⟨ⲡ⟩ l. 32; oblique stroke on ϥ l. 7; l. 2 ⲙⲛ stroke fixed before commit (preview); no dotted ϣ |
| 087 | 34 → 35 → 36 | 35 | read | 5861df0 | kephalaion 35 opens l. 14, title ll. 15–16; 36 opens l. 30, title ll. 31–32 (margin numerals on l. 31, corrected after review); "Am Rande … nicht lesbar" l. 4 (new id `margin-addition`); orphan ] l. 23; no dotted ϣ |
| 088 | 36 | 34 | read | b62d977 | l. 34 a lone numeral ⲗⲋ inside kephalaion 36 (number line, no milestone); block ▪ at the line end l. 21; dotted ϣ l. 9; page number ⲡ̣ⲏ̣ |
| 089 | 36 → 37 → 38 | 36 | read | 896c261 | kephalaion 37 opens l. 1 (numeral below the running title; "Die Zahl steht über", new id `number-position`), title l. 2; 38 opens l. 18, title ll. 19–20; "Lies ⲧϣⲁⲣⲡ" l. 5 (text as printed); dotted ϣ l. 23 ("ganz unsicher") |
| 090 | 38 | 33 | read | c761219 | \ⲱ/ l. 3; apostrophe l. 4; added-above words l. 17; conjecture/dittography l. 27; bare `[` ll. 15, 30; 4 ⲉⲕⲁϫⲟⲟⲥ fixed before commit (preview); no dotted ϣ |
| 091 | 38 | 33 | read | a94d22e | "Rechte Hälfte der Seite stark abgerieben" (page-condition, l. 1); dotted ϣ l. 4; mid-line "leer" l. 19; "Lies ⲛⲁⲧⲛ̄ⲕⲁⲧⲉ" l. 19 (text as printed); ⲧⲁⲡⲧⲏⲩ l. 28 (broken ⲡ leg, not ⲓ) |
| 092 | 38 | 33 | read | be1a00e | \ⲛ/ l. 2 ("übergeschrieben"); ⟦ⲛ⟧ l. 5 ("durch Punkt oben getilgt"); dotted ϣ l. 25; ϭⲱⲱ̣ⲛⲧ l. 27 (not ϣ, 8×); 14 ⲉϥⲁⲟⲩⲱⲥϥ fixed before commit (preview) |
| 093 | 38 | 34 | read | 497fafc | dotted ϣ ll. 10, 24; \ⲁ/ l. 33; enlarged Ⲡ mid-line l. 10; block ▪ at the line end l. 30; ⲓⲏⲥ bar over ⲏⲥ only l. 31 |
| 094 | 38 | 33 | read | 136ae03 | ⟨ⲟⲩ⟩ l. 3; "Ende ursprünglich" l. 10 (new id `app.original-reading`); «ⲛ̄ⲛ̣ⲉⲩ» sic l. 12 ("statt"); oblique tick over ⲕ l. 18; orphan ] l. 15; no dotted ϣ |
| 095 | 38 | 32 | read | ee96e6e | [ⲣⲁ(?)] split l. 14; two "[ blank ]" lines 31–32; "(?)" after ϣⲁⲩⲣ̄ϭⲁϫⲏ l. 32 (footnote "sehr unsicher"); smudged line-end ⲛ l. 23 fixed before commit (preview); no dotted ϣ |
| 096 | 38 | 33 | read | 94c7b88 | dotted ϣ l. 17; \ⲩ/ l. 5; ⲛ̄ϥ bars over the join measured on every line (both ≥ 50 % except 27); middot l. 25; correction "Lies ϣⲁϥϫⲡⲟ" l. 28 (text as printed) |
| 097 | 38 | 34 | read | 8cea4d5 | "Es müßte lauten" l. 2 (conjecture, `ec6ed70`); dotted ϣ ll. 6, 10, 26; orphan ] ll. 6, 30; oblique stroke on ϫ l. 29; mid-line "leer" l. 19; scan blemish between ll. 26/27 |
| 098 | 38 | 31 | read | 4abeaf1 | "Über ⲁⲃⲁⲗ etwas übergeschrieben" l. 8 (`82f0548`); ⟨ⲛ⟩ l. 2; block ▪ at the line start l. 23; bare `[` l. 11; oblique stroke on ϫ l. 18; no dotted ϣ |
| 099 | 38 | 33 | read | 0cfcb00 | ⟨ⲛ⟩ l. 2; "Lies ϣⲁⲣⲉ statt ϣⲁⲧⲉ" l. 9 (text as printed); ⲍ in ⲧⲍⲱⲛⲏ ll. 19, 23, 30; dotted ϣ ll. 10, 12; four sections after unmarked blanks with enlarged Ⲉ/Ⲧ |
| 100 | 38 | 33 | read | 29d478c | \ⲱ/ l. 18, \ⲛ/ l. 25 (footnote lemma with one ⲛ); [ⲃⲁ(?)] l. 25; separate bars over ⲃ ll. 26, 27, 31, 33; ϯ in ekthesis not enlarged l. 23; ⲙⲡⲟⲩⲑⲃⲓⲟ (no ⲧ, 6×) l. 31; no dotted ϣ |
| 101 | 38 | 34 | read | e6bc94f | grey blocks where the sense calls for ⲉ ll. 9 (line start), 30 (line end), pixel rows show no letter; ⟨ⲛ⟩ l. 18, ⟨ⲟⲩ⟩ l. 31; lone ϯ between words l. 21; dotted ϣ l. 17 |
| 102 | 38 → 39 | 36 | read | e6bc94f | kephalaion 38 ends l. 12 with `:—`; 39 opens l. 13, title ll. 14–15 (margin ⲗ̣[ⲑ]); "leer" inside a restoration l. 36 (`blank-probable`, `47e11e0`); unnumbered "— Lies ⲟⲩⲟⲩⲁⲣⲡ (Crum)" assigned to l. 25; dotted ϣ l. 16 |
| 103 | 39 | 33 | read | f1d5e52 | thick raised line-end stroke over ⲱ l. 3; smudged line-end ⲛ l. 18 (pixel rows); colon + "leer" at a section end l. 33; "Lies ⲛ̄ⲁⲓⲱⲛ" l. 21 (text as printed); dotted ϣ l. 24 |
| 104 | 39 → 40 | 35 | read | 4163fc1 | kephalaion 40 opens l. 21, title ll. 22–23 (left margin [ⲙ̄]); \ⲡⲉ ⲡⲙⲟⲩ/ l. 6; "ⲛ̄ϥ kleiner geschrieben" l. 3 (`60d3310`); ϩ̣̀ dot joined to the tail l. 10; square dot in a dot row l. 35; dotted ϣ l. 8 |
| 105 | 40 → 41 | 35 | read | c7755b1 | kephalaion 41 opens l. 15, title ll. 16–17; thick interline bar read as a stroke over ⲥⲗ l. 6; open ⲟ (reversed-ⲥ shape) in ⲩⲡⲟⲡⲟⲇⲓⲟⲛ l. 9; "in Ligatur" l. 4 (new id `app.ligature`, `7b147ed`); ⲛⲟ\ⲩ/ⲣⲏϩ l. 11; no dotted ϣ |
| 111 | 42 → 43 | 35 | needs audit | 1e28143 | pilot page |
| 159 | 65 | 33 | needs audit | 1e28143 | pilot page |
| 183 | 75 → 76 | 33 | needs audit | 1e28143 | pilot page |

Next unread page: **106**.

---

## 2. Open items

- **Audits** with the strict method (§3): 010–017, the pilot pages 049, 111, 159, 183, and 025–048, 050–100 (status "read").
  033 first: 33.20 had two letters the page does not print (ⲉⲧϩⲁⲥϫⲏϥ for ⲉⲧϫⲏϥ, found 2026-11-15). Every audit now
  includes `measure.py joins` and `spaces` (skill step 7a), which the pages before 035 never had.
- **ϯ or ⲯ in ⲯⲩⲭⲏ.** On 084–085 the first letter of ⲧⲯⲩⲭⲏ / ⲧⲉϥⲯⲩⲭⲏ has arms curving upwards and a stem through the baseline (8×),
  i.e. ⲯ, and is encoded ⲯ (82.21). Earlier pages encode the same word with ϯ (030, 031, 061, 063, 077: ϯⲩⲭ-; 080: ϯⲓⲥ). Audit
  those occurrences at 8× against a straight ϯ on the same page and correct them in an audit commit.
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
20. **Dots below the ink threshold (2026-11-15, 048).** On some pages whole dot rows are printed so pale that `measure.py dots`
   finds only a few blobs or none (048.11, 22, 23; 046.1–12); one dot can also fall apart into 1-px pieces (050.11 x 973).
   Count such rows only on 4× sheets in two overlapping halves, converting strip x to page x, and say in the `print` note that
   the count rests on the zoom. Never take the tool count.
21. **The print preview catches what the strips miss (2026-11-15).** On 050 the preview showed a letter written that the page
   does not print (050.2 ⲁⲣⲱⲟⲩ for ⲁⲣⲱⲩ) and a dot run one short (050.11). Compare every line of the preview with the scan
   before the review image, and re-zoom at 6–8× wherever the two differ.

22. **Pale pages (2026-11-16, 055).** Where a page is printed pale, strokes often stay above grey 130 on every row and the
   `strokes` detector misses them. Decided: such a stroke is confirmed at 6–8× and measured on a pixel map at grey < 170
   (or < 180); the threshold is stated in the `print` note. Single-letter strokes on such pages may rest on the zoom alone
   (055.24 ⲣ), which the note says.
23. **Dot runs across the strip join, again (2026-11-16).** 054.29 (9 → 8) and 055.28 (3 → 4) were miscounted where the two 4×
   halves overlap; both were caught by reconcile/spaces and fixed on a 5× zoom. Decided: every dot run that crosses
   x 880–960 is counted from the `dots` x-positions (or `spaces` gaps), never by adding the two halves by eye.
24. **Line 1 can be missing from `bands` (2026-11-17).** On 059 and 060 line 1 is a row of dots only, and the first band
   listed is l. 2. Decided: before reading, zoom on the strip between the running title and the first band and match the
   first band against the margin numeral "1"; the y of an all-dot line comes from `dots` on that strip.
25. **Reconcile still finds dotted ϣ the first draft missed (2026-11-17).** 56.5 (ⲙⲡϣⲁⲣⲡ) and 58.7 (ⲡⲁⲡϣⲁⲣⲡ) were written
   undotted at 4× and found only from a reconcile flag; 57.25 and 59.27 (a ϥ dot) from the 8× stroke and ϣ checks. Decided:
   the lower-zone ϣ sheet (item 13) is made before the first compile, not after, and every reconcile flag on a line with ϣ,
   ϥ or ϩ gets an 8× zoom of those letters.
26. **Long dot runs are counted from the positions (2026-11-18).** 065.31 had a run of 15 written as 14 by eye on a 2× sheet;
   reconcile caught it. Decided: every run of 10 or more dots is counted from the `dots` x-positions (pitch about 26 px), never
   by eye, and the first and last x go in the `print` note.
27. **Pale pages: position finder, zoom decides (2026-11-18, 062).** On a page printed pale, a blob finder at grey < 140–160
   (dilated by 1 px) gives one blob per dot where `measure.py dots` at 130 breaks dots into pieces of area 1–5. Decided: such a
   finder may be used to locate dots (the threshold goes in the note), the count is still checked on the 4× halves, and
   reconcile flags on that page are explained by the threshold.
28. **What a dotted ϣ is (2026-11-18, 62.2).** Specks that lie on the line of ϣ's tail (which curves down to the left) are not a
   dot. Decided: a ϣ is dotted only when a round dot stands inside or just below the lower bowl, apart from the tail, as in
   62.23, 62.26 and 63.17 (each compared at 8× with an undotted ϣ on the same page).
29. **Glyph boxes at the strip join (2026-11-19).** 069.29 ⲛⲉⲙⲉⲩ was written ⲛⲛⲉⲙⲉⲩ: the ⲛ at x 809–824 stood at the end of the
   left 4× half and the start of the right one and was read twice; `joins` did not show it (the word lay left of x 880), the print
   preview did. Decided: for every word that crosses x 800–960, count its letters against the glyph boxes of the line (one box per
   letter, ⲓ as a narrow box) before compiling; the joins sheet alone is not enough.
30. **Lines missing at the page top (2026-11-19, 070).** When the first lines of a page are rows of dots, the margin digits give the
   line y-values; a band list that starts at the second line is shifted by one (070: the first band was l. 2). Decided: on every page
   whose first band holds only dots, match the margin numerals "1" and "2" on a zoom before numbering (extends §3.24).
31. **Letters invented inside a word the zoom shows clearly (2026-11-20).** 073.24 ⲥⲉϩⲱⲩ was written ⲥⲉϩⲱⲟⲩ although the 4× strip was
   clear; only the print preview showed it. Decided: after drafting a line, count the letters of every word of six or more letters against
   the line's glyph boxes (`measure.py assign` or the scratch listing) before moving to the next line, not only at the strip join (§3.29).
32. **A dot written from memory of the neighbours (2026-11-20).** 074.29 had a dot under ⲣ of ϩⲛⲙⲟⲣⲫⲁⲩⲉ that the page does not print
   (the four dots stand under ⲫⲁⲩⲉ); reconcile caught it, and 073.22 had a dot under ⲗ of ⲁⲃⲁⲗ that the 8× zoom ruled out. Decided:
   every sublinear dot in a run of dotted letters is matched to a blob x-position (`dots`/`assign`) and the letter whose ink column holds it;
   the eye only proposes the run.
33. **Half a letter at the strip edge read as another letter (2026-11-21, 80.30).** The left 4× half ended inside the ⲡ of ⲡⲁⲏⲣ;
   its right half at the start of the right strip looked like ⲧ, and the word was first drafted "ⲡⲁⲧⲁⲏⲣ". Decided: wherever a word
   crosses x 770–800 or 1090–1110, the letters are counted against the glyph boxes before the line is written (extends §3.29 to both
   strip joins), and a letter that appears at the very start of a strip is accepted only if its glyph box starts there.
34. **Lines written from a sheet but never into the draft (2026-11-22, 082.29–34).** Six lines of 082 were read on the 4× strips
   but the draft stopped at l. 28; the review image showed the gap. Decided: before compiling, count the draft rows against the margin
   numerals of the page (the last numeral = the last row) — `validate.py` checks contiguity, not completeness at the end.
35. **ⲯ against ϯ (2026-11-22, 084).** The font prints ⲯ with arms curving up and a stem through the baseline, ϯ as a straight cross
   sitting on the baseline. Decided: every ϯ/ⲯ before ⲩⲭⲏ, ⲓⲥ or in ⲡⲙⲁϩⲯⲓⲥ is decided on an 8× zoom, never from the word.
36. **A letter dropped inside a clear word (2026-11-25, 090.4).** ⲉⲕⲁϫⲟⲟⲥ was drafted "ⲉⲕϫⲟⲟⲥ" from a clear 4× strip; only the print preview
   showed it. §3.31 asks for the count on words of six or more letters; this word has seven and the count was skipped. Decided: the
   per-line glyph-column listing (`cols`) is printed with every pair of 4× strips, and every word of five or more letters is counted
   against it before the line is written.
37. **A stroke decision written against its own measurement (2026-11-25, 086.2).** The pixel row gave ⲙⲛ 45 % / 50 % (→ ⲛ only), the note said
   so, but the draft line kept `ⲙ+ⲛ+`; the preview showed it. Decided: after writing a `print` note with a measured stroke, re-read the draft
   line and check that its markup says what the note decides.
38. **A letter misread from a clear 4× strip, again (2026-11-26).** 092.14 ⲉϥⲁⲟⲩⲱⲥϥ was drafted with ϣ for ⲥ, and 092.27 ϭⲱⲱ̣ⲛⲧ with a dotted ϣ
   for a tail-less ⲱ under a dot; the print preview and an 8× zoom caught both. Decided: every ϣ the draft writes is checked at 8× for its tail (a ϣ
   without a tail below the baseline is ⲱ or ⲥ), together with the dotted-ϣ check of item 13.
39. **A dark square at a line end is not a block until the pixel rows say so (2026-11-26, 095.23).** The line-end mark of 95.23 looked like a block at
   4× (a solid square at grey < 200), but at grey < 110 it shows the two legs and diagonal of ⲛ, and it begins ⲛ[ⲁⲅ]ⲅⲉⲗⲟⲥ of the next line. Decided:
   before a line-end block sign is encoded, its pixel rows are read at grey < 110–130 for letter strokes and the next line's first word is checked
   for a letter it could begin. (93.30 passes: a tapering solid mark 8 px wide with no strokes.)
40. **A broken letter is not two letters (2026-11-26, 091.28).** The right leg of ⲡ in ⲧⲁⲡⲧⲏⲩ is broken at its top and looked like ⲓ under a point at 4×.
   Decided: a "ⲓ" that stands where a two-legged letter's leg would be is checked on the pixel rows (bar continuity) before it is written.
41. **A letter seen only on the orientation sheet (2026-11-27, 100.31).** The 0.8× orientation sheet suggested ⲙⲡⲧⲟⲩⲑⲃⲓⲟ; the 4× strip and a 6× zoom show
   ⲙⲡⲟⲩⲑⲃⲓⲟ with no ⲧ. Decided: nothing is written from the orientation sheet; a word whose letter count differs between the orientation sheet and the 4×
   strip is zoomed at 6–8× and counted against its glyph columns.
42. **The top of ⲃ is not a stroke, a bar above it is (2026-11-27, 100.26).** The flat top of ⲃ is reported by `strokes` on almost every line; on 096–100
   these were all checked on the 4× strips and written off as "top of ⲃ". On 100.26, 27, 31, 33 a separate bar stands above ⲃ with a gap between (8×). Decided:
   a bar over ⲃ is encoded only when the 8× zoom shows it apart from the letter; the top of ⲃ alone is never a stroke.
43. **A pale round spot is not a printed mark (2026-11-27, 97.26/27).** A grey round spot between two lines (darkest grey 136 against about 70 for print) is a
   blemish of the scan. Decided: a spot whose darkest pixel is above grey 120 and that has no counterpart in the line's dot rhythm is not encoded; the note gives
   its position and grey value.
44. **A footnote reading is copied letter for letter, strokes included (2026-11-28, 103.21).** "Lies ⲛ̄ⲁⲓⲱⲛ" was first written as the reading ⲛⲁⲓⲱⲛ
   without its stroke; the print preview's apparatus line showed it. Decided: every `app` reading is compared with the footnote on a 2× zoom of the footnote
   block before compiling, including strokes and diaereses.
45. **A thick bar in the interline is measured against both lines (2026-11-28, 105.5/6).** A straight bar three rows thick between two lines (105: 530–569,
   rows 506–508) can be a stroke over the lower line or a mark under the upper one. Decided: it is compared with the raised strokes of the same page (gap to the
   x-height, thickness) and with both lines' letter extents; it is encoded by the ≥ 50 % rule on the line whose letters it covers and fits as a stroke, and the other
   reading is stated in the `print` note as a residual risk.
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
- Decided 2026-11-15 (pages 045–050):
  - Braced "bis auf geringe Spuren zerstört" (45.20–24) → `⁅=destroyed-traces:line⁆` on every line; "bis auf ganz geringe
    Spuren zerstört" (46.21–24) → `destroyed-traces-faint`. Destruction is named, so both are lost (new vocabulary ids).
    "nur geringe Spuren" (47.6) → `traces`. "die Spuren scheinen nicht recht zu x zu passen" (45.28) → `app.rejected`.
  - A restored letter printed after a braced statement on the same line (45.24 "[ⲙ̄]") → the statement, then the restoration.
  - An opening bracket before an enlarged letter with no closing bracket, followed by an extant dotted letter and a second
    opening bracket (45.26 "[Ⲡⲙ̣ⲁϩ[ⲥⲛⲉⲩ") → the first bracket is closed after the enlarged letter (`[^ⲡ]ⲙ_ⲁϩ[…]`), `bracket` note.
  - An editors' statement at a line start followed by an unpaired `]` and extant text (48.30 "unlesbar ]ⲙ̣ⲡⲕⲉⲕⲉ") →
    `⁅=ID⁆ ‡text`: the statement covers what precedes the bracket.
  - A single dot on the baseline after the last word, spaced like the illegible dots of the same line (45.33 "ⲡⲉ .") → one
    illegible letter, not a `point` sign.
  - A single-letter stroke that covers just under half of its only letter (46.15 ⲙ 48 %) is encoded on that letter, like
    §3.17: a printed stroke is never dropped; the % goes in the `print` note.
  - A nomen-sacrum bar over ⲡⲛⲁ that starts on the second ⲡ of ⲙⲡⲡⲛⲁ (50.23, 50.26: first ⲡ 0 %) → encoded on ⲡⲛⲁ only.
  - A footnote "x über der Zeile" where the edition prints x in the line (48.20 ⲡⲙⲟⲩ) → `\x/` + `app.added-above`, as 019.29.

- Decided 2026-11-16 (pages 051–055):
  - A dittography that runs over a line end (51.30 ϩⲁⲓⲛⲉ + 51.31 [ⲙⲉⲛ ⲛ]ϩⲏⲧ[ⲟⲩ]) is encoded as `{…}` on each line separately; a printed
    bracket that spans the end of the surplus is split at it (51.31 `{[ⲙⲉⲛ ⲛ]ϩⲏⲧ_[ⲟⲩ]} [ϩ]ⲁ…`), `bracket` note.
  - "Lies x" that only adds letters → `⟨⟩` in the text (51.26, 54.25). "Lies x statt y" where x only removes something printed
    (51.31: ⲙⲉⲛ for ⲙⲉⲛ̄, a stroke) → the text stays as printed; `app.correction` with the corrected form as reading.
  - New vocabulary ids: "auf Rasur" → `app.erasure` (51.10), "klein" without "über der Zeile" → `app.written-small` (51.14); both
    leave the text as printed. Variants: "oberhalb der Zeile" → `added-above` (52.16, 53.5); "Erg. vorher", "Auch … möglich",
    "Oder", "Lies vielleicht", "x von y, vielleicht z" → `conjecture`, nothing changed in the text (51.1, 52.33, 54.23, 53.21).
  - A raised thick vertical mark after a letter, from above the x-height to mid-letter (54.10 [ϩʼⲣⲉⲧⲟⲩ], 7 px wide), is an
    apostrophe sign like 27.1 and 52.20, also inside a restoration.
  - Two separate bars over ⲙⲛⲛ (54.20: one over ⲙⲛ, one over the second ⲛ) → `ⲙ+ⲛ+ⲛ-`, each bar decided on its own.
  - A large round point at mid-height between words, or after the last word before "leer" (51.14, 52.12, 52.19), → middle dot `·`.
  - An enlarged initial with a sublinear dot (55.19) → `^ⲡ_`; a two-legged enlarged ⲡ is one letter, however wide (8×).
  - A line of dots printed below the last numbered text line, with its own margin numeral (55.34), is a text line of
    illegible dots.

- Decided 2026-11-17 (pages 056–060):
  - Dots and restored letters inside one printed bracket pair ("[. . . . ϫ]", "[. . . . . ⲁ]", "[ⲛϩ . . . . ⲉ]", "ϩ[. . . . . .
    ⲡϣⲁⲣⲡ ⲛ̄]") → one restoration that holds the dots (`[....ϫ]`), `bracket` note (58.14, 59.5, 59.6, 59.18, 59.30, 60.31).
  - Letters printed before an unpaired `]` that the editors evidently restore ("ⲉⲕ]ⲗⲉⲕⲧⲟⲥ" 60.9, "ⲟⲩ]ϩ" 60.10, "ⲧ]ⲏⲣⲥ" 59.25) are
    encoded as read, as 29.28; the note says they look restored. A page whose left half is lost and marked by closing
    brackets only (60.2–12) is encoded line by line with `‡`.
  - A footnote printed after a dash with no line number of its own (57: "— Viell. am Ende …"; 60: "— oder ⲛⲟⲩ[ϭⲁⲙ]") is assigned
    by content to the one line whose text it fits (57.11, 60.30), `printed=N` with the preceding number, and the note says so.
  - Footnote numbers one line lower than the margin numerals on a page whose l. 1 is the chapter numeral (058: "17" = l. 18,
    "22" = l. 23, "25" = l. 26, "28" = l. 29) → `printed=N` on each row (§3.11); the shift is checked on every footnote.
  - "Lies x st. y" where x only adds a letter (59.9 ϣⲟⲩϣⲟⲩ for ϣⲟⲩϣⲟ) → `⟨ⲩ⟩` in the text, `app.correction`; "Lies x" that adds an
    article before the printed word (57.22, 59.3 ⲡⲁⲡⲙⲁϩϣⲁⲙⲧ) → `⟨ⲡⲁ⟩` before it.
  - "x [y]z fraglich" (58.23) → `app.conjecture` (vocabulary variant "… fraglich"), nothing changed in the text.
  - A small round point at the top of the x-height right after a letter, before a word space (58.29 ⲛⲉⲩ˙ ⲁⲃⲁⲗ, area 6) is a new sign
    type `high-point` (`˙`), not `point` (at or below line centre) and not a middle dot (large, mid-height, spaced like a word).
  - A dot under an enlarged initial (56.7 ⲡ̣, 56.30 ⲧ̣) → `^x_`, as 55.19, also when it lies below the zone where reconcile looks.

- Decided 2026-11-18 (pages 061–065):
  - A footnote on the state of a region of the page ("Die linke Hälfte der Seite stark abgerieben", 62.1) → `app.page-condition`
    (new id) at the line it is attached to, no lemma, no reading; the text keeps what is printed, nothing is turned into gaps.
  - "[ wohl leer ]" (64.32): an editors' statement inside brackets → `[⁅=blank-probable⁆]` (new id, reason lost: the brackets win;
    the editors think it was blank). Not `vac.`, because the blank is not seen.
  - "x wie im Boh." (64.22) → `app.parallel` (vocabulary variant), lemma the printed words, no reading.
  - A nomen-sacrum bar over ⲓⲏⲥ that starts on ⲏ (61.17: ⲓ about 25 %; 61.27, 64.2: restored ⲓ 0 %) → encoded on ⲏⲥ only, as printed
    (35.13, 50.23); the measured extent goes in the `print` note.
  - The end mark `:—` printed in the middle of a kephalaion, before a new section with an enlarged initial (64.1) → `§`
    (dicolon-dash) where it stands, like at a chapter end (183.9).
  - A printed mark of two ascending loops joined at the foot under a bar, after the last word (62.27) → new sign type `loop-mark`
    (`∾`) in `model.SIGNS`/`decompile.SIGNS`, skill table and §7.
  - "[ blank ]" at a line start followed by dots and text (65.22, 65.23) → `[⁅=uncounted⁆]`, as `[ ]` elsewhere.
  - A stroke over ⲙⲛ that covers ⲙ by exactly 50 % on the x-height band (65.29: ⲙ 50 %, ⲛ 57 %) → on both (the rule is ≥ 50 %).
  - A ⲡⲛⲁϭ ("the great") is never given a nomen-sacrum bar unless one is printed (61.29, 65.17): the bar is read, not inferred.
  - Dots printed closer than usual inside a bracket (63.8: six dots at about 20 px pitch) are counted as printed; the pitch goes
    in the note.


- Decided 2026-11-19 (pages 066–070):
  - An unclosed `[` with a restored letter and dots, followed by extant text on the same line (66.5 "ⲉⲧⲁⲛ̣[ϩ . . . . . ϩⲱϥ") → one
    restoration closed after the last dot (35.31 with 58.14). An unclosed `[` with restored letters and dots followed by extant letters
    and a second `[` (70.13 "[ⲧⲏⲥ . . . . . ⲟⲩⲭⲣⲟ[ⲛⲟⲥ]") → the first restoration is closed after the last dot (as 45.26).
  - A short arched stroke standing alone over ϥ (66.8 ⲉ]ⲧϥ̄ϣⲟⲟⲡ, 8×) is a stroke and is encoded on ϥ; an oblique stroke over ⲗ
    (70.19, 70.24, 70.26 ⲛⲗ̀ⲗⲟⲗⲉ, ⲁⲛⲃⲗ̀ⲃⲓⲗⲉ) is encoded like the oblique strokes over ⲥ and ϩ (`ⲗ'`).
  - A ϯ at the start of a line in ekthesis whose height is ordinary and only its cross-bar long (67.11) is not an enlarged letter.
  - Unmarked blanks: a blank of 40 px or more (about twice an ordinary word space of 18–23 px) is `%` (67.18: 76 px, 67.20: 41 px); a
    blank below 40 px is an ordinary word space (68.17: 31 px). The width goes in the `layout` note.
  - A small solid block standing in a row of dots where a dot would be (68.4, before ⲙⲙⲁϥ) → block sign `▪` (31.28).
  - Two closing brackets for one opener (68.6 "[ϩⲙ̄ ⲡ]ⲕⲟⲥⲙ]ⲟⲥ") → the first closes the restoration, the second is an unpaired `‡`; encoded
    as printed with a `bracket` note.
  - A sublinear dot printed at the foot of the stem of ⲫ, right of it (68.7), belongs to ⲫ (as the ⲣ dot of 41.11).
  - "x Qual. zu y" (68.25) → `app.grammar` (new vocabulary id): the editors explain a form without doubting it; text unchanged.
  - A chapter numeral standing centred between two margin numerals with no text on either line (70.8–9) → the numeral on the upper
    line (30.14) and the other line encoded as `vac.` with a `layout` note. A bar printed below a chapter numeral (centred or marginal)
    is a frame line and is not encoded; the bar above stays the numeral's stroke, as on every chapter numeral (70.8, 70.10).
  - An enlarged letter at a line end (70.14 Ⲛ̄[ⲧⲁ], 28 px high against 14 px) → `^ⲛ-`, encoded as printed.
  - A dot under ϯ, separate from its foot (70.28), is a sublinear dot of ϯ.

- Decided 2026-11-20 (pages 071–075):
  - An enlarged letter with a stroke at a line end, after an unmarked blank, that begins the first word of the next line (71.14 "% Ⲛ̄" →
    l. 15 Ⲛ̄ⲧ[ⲁϥ]) → `% ^ⲛ-` where it stands (70.14); the word is not joined across the line.
  - A small solid block at the start of the text column before a word (73.3), or standing at the dot pitch in a row of dots before a word
    (75.8, printed with a darker frame and a lighter centre) → block sign `▪` (68.4), not a letter and not a dot.
  - "Lies x" or "Lies x statt y" where x removes printed letters (73.29 ⲛⲛⲁⲡⲟⲥⲧⲟ → ⲛⲁⲡⲟⲥⲧⲟⲗⲟⲥ; 73.18 ϩⲓϫⲉⲛ → ϩⲓϫⲛ̄) → the text stays as printed;
    `app.correction` with the corrected form as reading (extends 51.31 from a stroke to letters).
  - "Über dem x noch ein y" (75.9: an ⲛ above an ⲉ) when the line holds several x and the footnote does not say which → the text stays as
    printed; `app.added-above` with lemma x and reading y, the ambiguity in the note (vocabulary variant, `b54413c`). Where the footnote
    names the place ("ⲡⲙⲁ, ⲙ üb. d. Zeile", 71.30) the letter is encoded `\x/` as before (48.20).
  - One footnote with two statements ("Lies ⲥϩⲛⲏⲩⲧ, Qual. von ⲥⲁϩⲛⲉ", 72.29) → two app rows on the same line, one per id (`correction`,
    `grammar`); "Qual. von" is a variant of `grammar`.
  - An enlarged initial that the editors restore inside the bracket at a line start ([Ⲡⲙⲁϩⲥⲛⲉⲩ …] 75.13, 75.20, 75.24, 75.32; [Ⲧϩⲉ …] 72.7;
    [Ⲉⲣ]ϣⲁⲛ 74.7) → `[^x…]`, and the line is in ekthesis when its bracket stands left of the text column.
  - A stroke over a ⲛⲛ / ⲙⲛ / ⲛϥ pair measured at exactly 50 % on one letter (72.29 ⲛ 50 %, 75.34 ⲙ 50 %) → on both (65.29).

- Decided 2026-11-21 (pages 076–080):
  - A printed sign standing inside a lacuna between its dots (76.9: a raised vertical mark after the first dot of "ⲉⲧⲁ[. ʼ. . . . .]") →
    the sign is encoded where it stands, inside the restoration (`[.ʼ.....]`).
  - "Überschrift ganz verwischt" centred in the two title lines (76.16–17) → `⁅=smeared-wholly:line⁆` on each title line (new vocabulary
    id `smeared-wholly`, "ganz verwischt": illegible).
  - The blank before an enlarged letter is measured over the full letter height (crossbar included), not only the x-height band; ≥ 40 px
    → `%` (76.31: 55 px; 78.25: 55 px); below 40 px an ordinary space (76.23, 77.34, 78.11).
  - A separate short bar over a final ϥ (76.35, 77.5, 77.18, 78.2) is a stroke on ϥ (`ϥ-`), like the arched stroke of 66.8.
  - A small round point standing alone at mid-height in a word space (77.31, area 6 at grey < 170) is a middle dot `·` whatever its size;
    the size goes in the note.
  - A bar running obliquely down to the right over ⲡ (78.33 [ⲡ̀ϭⲱⲛⲧ]) → oblique stroke `ⲡ'`, like ⲥ, ϩ and ⲗ (70.19).
  - A "(?)" printed after a word whose only uncertain part is a restoration (79.1 "[ⲛϣ]ⲧⲉⲕⲟ(?)") → the doubt goes on the restoration,
    `[ⲛϣ(?)]ⲧⲉⲕⲟ`.
  - A round dot centred between the legs below an enlarged Ⲡ (80.5, area 4; 80.25, area 10) → `^ⲡ_` (55.19), also when it is small.
  - Two bars over one group (80.22 ⲛ̄ⲓ̈ⲏⲥ: a long bar over ⲛⲓⲏⲥ and a short bar under it over ⲛ alone) → the long bar is encoded by the
    ≥ 50 % rule on every letter it covers (ⲛ 85 %); the second bar over ⲛ cannot be a second stroke on one letter and is recorded in the
    `print` note.
  - A bare `[` at a line end with no closer on the next line, which opens with illegible dots (80.22) → `[⁅=open-bracket⁆]` (75.13).
  - A line whose word spaces are set tight (79.22: 11–16 px) keeps the printed word division; `spaces` (≥ 14 px) is explained by the widths.
  - Footnote formulas (vocabulary variants, `1e8247c`): "Bedeutung von … unbekannt" and "unbekannt" → `app.sic` (76.9, as 31.7);
    "Lies wohl" → `app.conjecture` (76.33, text unchanged); "oder … zu erg." → `app.conjecture` (78.4, existing "… oder …").
  - "Lies x" where x removes a printed letter (77.9 ⲛⲛⲣⲣⲟ → ⲛⲣⲣⲟ, 78.21 ⲁⲩⲡⲡⲗⲁⲥⲥⲉ → ⲁⲩⲡⲗⲁⲥⲥⲉ, 80.24 ⲛⲉⲧⲧϭⲣⲁⲓⲧ → ⲛⲉⲧϭⲣⲁⲓⲧ) → text as printed,
    `app.correction` (73.29); "Lies x" adding a letter with its stroke (80.18 ⲛ̄ⲕⲣⲓⲧⲏⲥ) → `⟨ⲛ-⟩` in the text.

- Decided 2026-11-22 (pages 081–085):
  - "Lies x oder y" without a question mark (81.24) → `app.conjecture` with both forms as readings, text unchanged (39.24; vocabulary
    variant `5af5d7b`).
  - "Über x zwischen den Zeilen: y" (82.25), words added between the lines whose place in the text is not named → text unchanged,
    `app.added-above` with x as lemma and y as reading (75.9; vocabulary variant `5af5d7b`). Where the footnote names the place inside one
    word ("ϩⲟⲩⲓⲧⲉ, ⲟⲩ oberhalb der Zeile" 84.4; "In ⲉϥⲥⲁⲡⲥ über der Zeile ⲡ" 85.8) → `\x/` (48.20).
  - A short oblique stroke over ϥ (81.15, 84.28, 84.29) or a tick over ⲁ (82.12) → oblique stroke `x'`, like ⲥ, ϩ, ⲗ, ⲡ (70.19, 78.33).
  - Two bars over ⲛⲓⲏⲥ, one over ⲛ and one over ⲏⲥ with ⲓ bare (82.33) → `ⲛ-ⲓⲏ+ⲥ+`, each bar on the letters it covers.
  - Two opening brackets at a line end with no closer (84.17 "[ϩⲛ̄[") → `[ϩⲛ- ⁅=open-bracket⁆]`: one restoration closed at the line end that
    holds the second, bare bracket (44.5, 80.22); the space keeps the stroke apart from the token.
  - A word turned over into a line of its own at the right, with its own margin numeral (85.35 ⲙ̄ⲡⲣⲓⲉ) → a text line (55.34), `layout` note.
  - Unmarked blanks before the closing ornament of a title line follow the 40 px rule (84.6: 133 px, 84.7: 98 px, 85.21: 50 px → `%`).
  - A blank of 34–37 px before an enlarged letter in the line (82.29 Ϣⲁⲙⲧ, 82.34) is an ordinary space (76.31).

- Decided 2026-11-25 (pages 086–090):
  - A line that holds only a centred kephalaion numeral while that kephalaion is already in progress, with no title after it (88.34: ⲗⲋ after
    kephalaion 36 opened at 87.30) → a `number` line without `kephalaion=N`, so no new milestone; `layout` note.
  - A kephalaion numeral printed as line 1 right below the running title (89.1) is the chapter opening; a footnote "Die Zahl steht über x"
    → `app.number-position` (new id): lemma the numeral, reading x, text unchanged.
  - "Am Rande klein nachgetragen ein Satz …, aber nicht lesbar" (87.4) → `app.margin-addition` (new id), no lemma and no reading.
  - Margin numerals of a chapter opening are compared with each other and with the title lines on a 2× zoom of the whole opening, not from
    per-side column extents. 87.31/32 was first encoded with the left numeral on l. 31 and the right one on l. 32; the user pointed out that
    both stand between the two title lines at the same height, as everywhere else, so both go on l. 31 (30.14; corrected in `5861df0`).
    `render_print.py` keeps the guard for a line with one side only (`970e4ef`), which that misreading had exposed.
  - A "(?)" printed after a word whose restoration holds dots and letters (89.12 "[. . . ⲥⲱ]ⲧⲙⲉ (?)") → the doubt goes on that restoration,
    `[.........ⲥⲱ(?)]ⲧⲙⲉ` (79.1 with 58.14).
  - "Lies x" where x replaces a printed letter (89.5 ⲛϣⲁⲣⲡ → ⲧϣⲁⲣⲡ) → text as printed, `app.correction` (73.29).
  - Vocabulary variants (`05bc744`, ids unchanged): "In x steht y über der Linie" → `added-above`, `\y/` (90.3); "Hinter x klein über der
    Zeile: y" → `added-above`, text unchanged (90.17, as 82.25); "Von x nur ganz unsichere Spuren" → `uncertain-strongly` (90.15); "(Anfang) x
    nur unsichere Spuren" → `uncertain` (90.19).
  - A raised comma-shaped mark after a final ⲧ, above the x-height (90.4 ⲛ̄ⲕⲧⲟⲩⲛⲟⲩⲓ̈ⲉⲧʼ) → apostrophe sign (27.1).

- Decided 2026-11-26 (pages 091–095):
  - "Rechte Hälfte der Seite stark abgerieben" (91, unnumbered) → `app.page-condition` at l. 1 (62.1; vocabulary variant `41ab7ed`).
  - "x in y übergeschrieben" (92.2 ⲛ in ⲁⲛ) → `\x/` at its place + `app.added-above` (vocabulary variant `5f50928`).
  - "x, lies y, z durch Punkt oben getilgt" (92.5: ⲕⲱⲛ, lies ⲕⲱ) → `⟦z⟧` on the letter the edition prints, here the first ⲛ of ⲛⲛϩⲏⲧⲟⲩ, although no point
    and no double brackets are printed (33.12; vocabulary variant `5f50928`).
  - "Ende ursprünglich x" (94.10) → new id `app.original-reading`: the scribe's earlier form; text as printed, lemma the printed words, reading x (`afbcf57`).
  - "x statt y" without "Lies" (94.12 ⲛ̄ⲛ̣ⲉⲩ statt ⲁⲛⲉⲩ) → `«x»` + `app.sic` with y as reading, as "x sic für y" (39.5; `afbcf57`).
  - A short oblique tick over the upper arm of ⲕ, apart from the letter (94.18 ϥⲥⲁⲃⲕ̀) → oblique stroke `ⲕ'` (82.12).
  - A queried restoration and a dot run with a restored letter in one bracket pair (95.14 "[ⲣⲁ(?) . . . . . . ⲥ]") → `[ⲣⲁ(?)] [......ⲥ]` (27.12 with 58.14).
  - A "(?)" printed after an extant word (no restoration) whose doubt a footnote states (95.32 ϣⲁⲩⲣ̄ϭⲁϫⲏ(?), "Lesung … sehr unsicher") → no sign and no
    change in the text; the apparatus row (`uncertain-strongly`) carries it and its note says the "(?)" is printed.
  - "der 2. Buchst. ganz unsicher; sonst x" (95.18) → one `app.uncertain-strongly` row with x as reading.
  - An enlarged initial in mid-line after an ordinary word space (93.10 Ⲡⲉⲧⲟ, 30 px) opens a section with no `%` (76.31).

- Decided 2026-11-27 (pages 096–100):
  - "Es müßte lauten: x" (97.2, a rewording over three lines) → `app.conjecture` with x as reading, text unchanged (vocabulary variant `ec6ed70`).
  - "Über x etwas übergeschrieben" (98.8) → `app.added-above` with x as lemma and no reading, text unchanged (as 20.25; vocabulary variant `82f0548`).
  - A footnote "x, y über der Zeile" whose lemma x is shorter than the printed word and holds one y (100.25 "ⲛϩⲁⲙⲧ, ⲛ" for ⲉⲩⲛⲛϩⲁⲙⲧ) → `\y/` on the y that
    the lemma begins or contains (here the second ⲛ, before ϩ).
  - A short oblique stroke over ϫ (97.29 [ⲣ]ϫ̣̀, 98.18 ⲛϥⲡⲱⲣϫ̀) → oblique stroke `ϫ'`, like ⲥ, ϩ, ⲗ, ⲡ, ϥ, ⲁ, ⲕ.
  - ⲍ is read where the letter has a flat top bar and a zigzag body with a tail (99.19, 23, 30 ⲧⲍⲱⲛⲏ), decided at 8× against ϩ on the same line.
  - A bar over ⲛϥ / ⲙⲛ / ⲛⲛ / ⲧϥ printed over the join (096 throughout): each letter is measured on the pixel row; both ≥ 50 % → both (96.20, 99.9);
    one below 50 % → the other only (96.27 ϥ, 96.2 ⲛ). No change to §3.17.

- Decided 2026-11-28 (pages 101–105):
  - A grey filled box where the sense calls for a letter (101.9 at a line start before ϩⲙ, 101.30 at a line end after ⲁⲛⲁⲕ; both where ⲉ is expected) is a block `▪`
    when its pixel rows at grey < 95–110 show only a darker frame and no letter strokes (§3.39); one that shows the legs and diagonal of a letter is that letter
    (103.18 line-end ⲛ, as 95.23). The sense is never used to turn a block into a letter.
  - A ϯ standing alone between two words, 16–17 px wide like the page's ϯ (101.21 ⲛⲁⲡⲟⲥⲧⲟⲗⲟⲥ ϯ ⲟⲩ, 103.31 ⲛⲧⲛⲁϭ ϯ ⲏⲡⲉ), is the letter ϯ, not the cross sign (39.19, 23 px).
  - The end mark `:—` at the end of a kephalaion (102.12, end of 38) → `§` (183.9).
  - "leer" printed inside one restoration between restored words (102.36 "ⲛ̣[ϣⲏⲣⲉ leer ⲡϣⲁⲣⲡ ⲙ̄ⲙⲟⲩ]") → `⁅=blank-probable⁆` inside the restoration (vocabulary variant
    `47e11e0`), not `vac.`.
  - A thick bar raised 10–12 px above a line-end letter (103.3 ⲡⲁⲅⲱ̄, 105.26 ⲛⲛϩⲓⲕⲱ̄) is a supralinear stroke on that letter by the ≥ 50 % rule; the height and thickness
    go in the `print` note. A thick bar in the interline over the first letters of a line (105.6 ⲥ̄ⲗ̄ϭⲉ, 13 px above the x-height) is encoded the same way (§3.45).
  - "x kleiner geschrieben, wohl nachgetragen" (104.3 ⲛ̄ϥ) → `app.written-small`, text as printed (`60d3310`); "x y über der Zeile" for two whole words (104.6 ⲡⲉ ⲡⲙⲟⲩ)
    → `\x y/` (48.20); "In x steht y über der Zeile" (105.11) → `\y/` (90.3).
  - "x in Ligatur" (105.4, ⲥⲧⲁⲩ|ⲣⲉ over a line end) → new id `app.ligature`: lemma the printed word, no reading, text unchanged (`7b147ed`).
  - Letters standing alone between illegible dots (104.12 "[. . .] ⲙ . ⲗ̣ . .", 104.14 ". . . ϫ . ⲩ ⲙⲛ . . .") are written as separate tokens spaced as printed.
  - A dot printed square in a row of round dots, of the same size, darkness and pitch (104.35, 4×5 px), is an ordinary illegible dot, not a block (contrast 75.8, a block
    with a darker frame).
  - A letter printed with one side missing so that it looks like another shape (105.9 an ⲟ with its left arc unprinted, a reversed-ⲥ shape the font does not have) is
    encoded as the font's letter whose remaining strokes it shows, with a `print` note (§3.40); not as ⲥ.
  - The left marginal chapter numeral printed in restoration brackets (104.22 [ⲙ̄]) → `[ⲙ-]` in the margin row; the right one as printed.

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
- 2026-11-16: `lxml`, `scipy` and `playwright==1.63.0` had to be installed for `python` (3.11) again, and Pillow with
  `--ignore-installed`. The worker restarted once (during p. 054, after a usage-limit pause); drafts, images and installed
  packages survived and work went on from the draft.
- 2026-11-17: as on 2026-11-16, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with
  `--ignore-installed`. No restart. A scratch helper (pixel-row bar extents and x-height ink columns per line) was used for
  the ≥ 50 % stroke rule; it is not part of the repository tools.
- 2026-11-18: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with
  `--ignore-installed`. No restart. Scratch helpers (not in the repository): pixel-row bar extents with x-height ink columns
  (≥ 50 % rule), and a dilated blob finder at grey < 140–160 for the pale p. 062 (§3.27).

- 2026-11-20: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with `--ignore-installed`.
  No restart. One Drive download timed out (p. 074) and succeeded on the second call. Scratch helpers (not in the repository): per-line
  dot/bar/ink-column listing with per-letter bar coverage, and a scan for small blobs inside a letter's box (dotted-ϣ candidates).

- 2026-11-19: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with
  `--ignore-installed`. No restart. Scratch helpers (not in the repository): per-line dot/bar/glyph-box listing, pixel-row bar extents
  with x-height ink columns (≥ 50 % rule), and a word-gap check that ignores dot neighbours.

- 2026-11-21: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with `--ignore-installed`. No
  restart. Scratch helpers (not in the repository): per-line glyph columns / dots / bar extents with per-letter coverage, and per-row bar
  extents for the ≥ 50 % rule.

- 2026-11-22: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with `--ignore-installed`. No
  restart. Images 081–085 downloaded from Drive (1553×2258). Scratch helpers (not in the repository): per-line glyph columns / dots / bar
  extents with per-letter coverage, per-row bar extents, and blank widths over the full letter height.
- 2026-11-25: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with `--ignore-installed`. No
  restart. Images 086–090 downloaded from Drive (1553×2258; the connector saved each to a tool-results file, copied into place). Scratch
  helpers (not in the repository): per-line glyph columns / dots / bar extents with per-letter coverage, and per-row ink extents.
- 2026-11-26: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with `--ignore-installed`. Images 091–095
  downloaded from Drive (1553×2258; saved by the connector to tool-results files and copied into place). The worker restarted once (during p. 095,
  after its first compile); drafts, images and packages survived and work went on from the draft. Scratch helpers (not in the repository): per-line
  glyph columns / dots / bar extents with per-letter coverage, and per-row ink runs at a chosen grey threshold.
- 2026-11-27: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with `--ignore-installed`. Images 096–100 downloaded
  from Drive (1553×2258; saved by the connector to tool-results files and copied into place). No restart. Scratch helpers (not in the repository): per-line glyph
  columns / dots / bar extents with per-letter coverage, per-x ink counts and per-row ink runs for the ≥ 50 % rule, and a three-strip 4× zoom wrapper.
- 2026-11-28: as before, `lxml`, `scipy` and `playwright==1.63.0` installed for `python` (3.11) and Pillow with `--ignore-installed`. Images 101–105 downloaded from Drive
  (1553×2258; saved by the connector to tool-results files and copied into place). No restart. Scratch helpers (not in the repository): per-line glyph columns / dots /
  bar extents with per-letter coverage, an ASCII pixel map at a chosen grey threshold, a crop-sheet builder for ϣ checks and a three-strip 3.6× zoom wrapper.
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
- **2026-11-15** — Routine run (third): read 045, 046, 047, 048, 050 on `reading/2026-11-15` (049 was read before as a pilot
  page). All five validate "ok"; all 44 pages re-validated after the vocabulary change. Reconcile flags explained: dots of area
  < 6 or below the ink threshold (most of 046–048, 050), dot rows at the zone centre, umlauts of German statements (046.22,
  046.26, 047.34), feet of marginal numerals (046.14), a dotted restored letter (046.17). Dotted ϣ accepted after 8× comparison:
  046.16, 050.25; none on 045, 047, 048. Caught before commit by the print preview: 050.2 ⲁⲣⲱⲟⲩ → ⲁⲣⲱⲩ, 050.11 a dot run one
  short. Vocabulary (`8b33497`): new ids `destroyed-traces`, `destroyed-traces-faint`; German variants "nur geringe Spuren"
  (traces) and "die Spuren scheinen nicht recht zu … zu passen" (rejected). Method §3 items 20–21; encoding decisions in §4.
  No new sign types. Images downloaded from Drive (1553×2258); Pillow again needed `--ignore-installed`. No pages skipped.

- **2026-11-16** — Routine run: read 051–055 on `reading/2026-11-16`. All five validate "ok"; all 49 pages re-validated after the
  vocabulary change (`dd7e92e`: new ids `erasure`, `written-small`; variants for added-above and conjecture; correction
  judgement for "Lies x statt y"). Reconcile flags explained: dot rows at the zone centre, dots of area < 6 or below the ink
  threshold (most of 055, a pale page), margin numerals (052.24, 053.2/12/32), tails of ϩ (055.13/30), a dotted letter inside
  the surplus (051.31). Caught before commit: 054.29 dot run one too many and 055.28 one too few at the strip join (§3.23).
  Dotted ϣ accepted after 8× comparison: 051.9, 052.12, 053.8, 053.29, 054.27; none on 055. Kephalaion 17 opens 55.16; kephalaion 16
  ends 55.15 with no end sign (dots + "leer"). Method §3 items 22–23; decisions §4 (2026-11-16). No new sign types. Images
  downloaded from Drive (1553×2258). No pages skipped.

- **2026-11-17** — Routine run: read 056–060 on `reading/2026-11-17`. All five validate "ok"; all 61 pages re-validated after
  each tool/vocabulary change. Tool (`dd6ac9d`): new sign type `high-point` in `model.SIGNS`/`decompile.SIGNS` and the skill's
  sign table (58.29). Vocabulary (`a2e293c`): "… fraglich" → `app.conjecture` (id unchanged). Reconcile flags explained: dot rows
  at the zone centre (056.16/18/33, 057.14, 059 most lines, 060.1/10), dots of area < 6 (060 ll. 2–11, 059.19), dots joined to ⲓ,
  ϥ or ϩ (057.17/26, 059.5/27), feet of ⲙ/ϭ (056.1), margin numerals (057.28, 060.14), a fragment of ⲓ (060.24). Caught by reconcile
  before commit: dotted ϣ 56.5 and 58.7, ϥ̣ 58.31, ⲓ̣ 59.12, a run of 13 not 12 (56.34). Dotted ϣ accepted after 8× comparison:
  056.5, 057.25, 058.2, 058.5, 058.7, 058.30; none on 059, 060. Kephalaion 17 ends 057.32 (dots, page end) and 18 ends 060.12
  (dots) with no end sign; 18 opens 58.1, 19 opens 60.13. Method §3 items 24–25; decisions §4 (2026-11-17). Images downloaded from
  Drive (1553×2258). No pages skipped.

- **2026-11-18** — Routine run: read 061–065 on `reading/2026-11-18`. All five validate "ok"; all 60 pages re-validated after each
  tool/vocabulary change. Tool (`4b0a62c`): new sign type `loop-mark` (62.27) in `model.SIGNS`/`decompile.SIGNS` and the skill's
  sign table. Vocabulary (`a2fff82`): new id `app.page-condition` (62.1); (`b253242`): new id `ed.blank-probable` (64.32) and
  "wie im Boh." as a variant of `app.parallel` (64.22). Reconcile flags explained: dots of area < 6 or below the ink threshold (most of
  062, a pale page; 061.1; 063.10–13; 064.22–31; 065.1–11), dot rows at the zone centre (061.3–7, 061.25, 064.34, 065 title lines),
  margin numerals (061.2/12, 063.20, 064.14, 065.29), pieces of German (061.16, 062.29/31, 064.32, 065.19/24), a bowl dot inside ϣ
  (062.23/26, 063.17), dots joined to ϥ or ⲣ (062.18, 065.23). Caught before commit: a dot under ⲩ missed at 61.28 (reconcile), a run of
  15 written as 14 at 65.31 (reconcile). Dotted ϣ accepted after 8× comparison: 062.23, 062.26, 063.17; none on 061, 064, 065.
  Kephalaion 19 ends 063.18 (dots), 20 ends 064.12 ("leer"), 21 ends 065.13 (ϣⲁ ⲁⲛⲏϩⲉ + "leer"), none with an end sign; 20 opens
  63.19, 21 opens 64.13, 22 opens 65.14. Method §3 items 26–28; decisions §4 (2026-11-18). Images downloaded from Drive (1553×2258).
  No pages skipped.

- **2026-11-19** — Routine run: read 066–070 on `reading/2026-11-19`. All five validate "ok"; all 64 pages re-validated after the
  vocabulary change (`3c01ab9`: new id `app.grammar`, "Qual. zu", 68.25). Reconcile flags explained: dot rows at the zone centre (most
  flags on every page), dots of area < 6 (068.1–3, 068.12, 070.3/5), dots below the zone window (066.11, 069.25/29), pieces of "leer"
  (067.3/30, 069.16), margin numerals (069.22, 070.2), a detached stroke end (068.29), a dotted restored letter (070.14). Caught before
  commit: 069.29 ⲛⲛⲉⲙⲉⲩ → ⲛⲉⲙⲉⲩ (letter read twice at the strip join, found on the print preview; §3.29), 070.24 a space before a
  bracket set close to ϩ. Dotted ϣ accepted after 8× comparison: 067.5, 067.29, 069.17, 070.28; none on 066, 068. Kephalaion 22 ends
  066.27 (dots) and 23 ends 070.7 (dots + "leer"), neither with an end sign; 23 opens 66.28, 24 opens 70.8. Method §3 items 29–30;
  decisions §4 (2026-11-19). No new sign types (one more block, 68.4). Images downloaded from Drive (1553×2258). No pages skipped.

- **2026-11-20** — Routine run: read 071–075 on `reading/2026-11-20`. All five validate "ok"; all 69 pages re-validated after the
  vocabulary change (`b54413c`: variants "üb. d. Zeile" and "Über dem … noch ein …" → `added-above`, "Qual. von" → `grammar`; ids
  unchanged). Reconcile flags explained: dot rows at the zone centre (most flags on every page), dots of area < 6 (075.1/7/15, 074.26),
  margin numerals (073.20/23/28/29, 075.32), the "?" point (071.8), dotted restored letters (071.24, 073.8), the block sign (075.8).
  Caught before commit: 073.24 ⲥⲉϩⲱⲟⲩ → ⲥⲉϩⲱⲩ (print preview), 074.29 a dot under ⲣ the page does not print (reconcile), 073.22 a dot
  under ⲗ ruled out at 8×. Dotted ϣ accepted after 8× comparison: 073.22, 074.3, 075.29, 075.30; none on 071, 072. Kephalaion 24 runs
  through all five pages (opened 70.8); new sections open after "leer" or in ekthesis with enlarged letters, five times with Ⲡ on 075.
  Method §3 items 31–32; decisions §4 (2026-11-20). No new sign types (two more blocks, one more middle dot). Images downloaded from Drive
  (1553×2258). No pages skipped.

- **2026-11-21** — Routine run: read 076–080 on `reading/2026-11-21`, branched from `reading/2026-11-20` because PR #15 (071–075) was still
  open and unmerged (076 continues from 075). All five validate "ok"; all 74 pages re-validated after the vocabulary change (`1e8247c`: new
  id `smeared-wholly`; variants "unbekannt" / "Bedeutung von … unbekannt" → `sic`, "Lies wohl" → `conjecture`). Reconcile flags explained:
  dot rows at the zone centre (076.1/3/12, 078.13/18, 079.31, 080.12/13/16/21/23), margin numerals (076.15/27, 077.3/5/15/23, 079.3/14/29),
  the German statement in the title lines (076.16), dots below the zone window (077.1/21), dots of area < 6 (077.30, 078.3/4, 080.5/10),
  a detached stroke end (080.11). Caught before commit: 080.30 "ⲡⲁⲧⲁⲏⲣ" → ⲡⲁⲏⲣ (half a ⲡ at the strip edge read as ⲧ; glyph boxes, §3.33).
  Dotted ϣ accepted after 8× comparison: 077.21, 078.3, 079.8, 079.19, 079.23, 079.28 (two), 080.10; none on 076. Kephalaion 24 ends 076.14
  ("leer"), 25 ends 076.25, 26 ends 077.21, 27 ends 079.12 (ϣⲁ ⲁⲛⲏϩⲉ + "leer"), none with an end sign; 25 opens 76.15, 26 opens 76.26,
  27 opens 77.22, 28 opens 79.13. Method §3 item 33; decisions §4 (2026-11-21). No new sign types (one more apostrophe, one more middle
  dot). Images downloaded from Drive (1553×2258). No pages skipped.

- **2026-11-22** — Routine run: read 081–085 on `reading/2026-11-22`. All five validate "ok"; all 85 pages re-validated after the
  vocabulary change (`5af5d7b`: variants "Lies … oder …" → `conjecture`, "Über … zwischen den Zeilen" → `added-above`; ids unchanged).
  Reconcile flags explained: dots at the zone centre (most flags), dots of area < 6 (081.24, 082.14/15/28, 084.12/16/21, 085.2), dots cut
  by the lower edge of the zone window (081.26, 082.1/20/21/24/31, 083.9/14), margin numerals (081.22), pieces of "leer" (081.28, 082.27,
  084.20, 085.29), broken letter feet (081.9, 084.14, 085.27/30). Caught before commit: 082.29–34 missing from the draft (review image;
  §3.34); 084.4 and 085.8/17 footnotes first left unencoded (print preview); 084.34 bracket note corrected (closer printed). Dotted ϣ
  accepted after 8× comparison: 083.28, 085.16, 085.22, 085.33; none on 081, 082, 084. Kephalaion 28 ends 081.20 (ϣⲁ ⲁⲛⲏϩⲉ + "leer"),
  29 ends 083.16 ("leer"), 30 ends 084.4, 31 ends 085.18, none with an end sign; 29 opens 81.21, 30 opens 83.17, 31 opens 84.5, 32 opens
  85.19. Method §3 items 34–35; decisions §4 (2026-11-22); new open item ϯ/ⲯ (§2). No new sign types (one more block, 83.5). No pages
  skipped.

- **2026-11-25** — Routine run: read 086–090 on `reading/2026-11-25`. All five validate "ok"; all 90 pages re-validated after each tool and
  vocabulary change. Tool (`970e4ef`): `render_print.py` crashed on a line carrying only a right margin numeral (87.32, itself a misreading: corrected after review in `5861df0`, both numerals on l. 31); the guard stays. Vocabulary:
  new ids `app.margin-addition` (`6aadda7`, 87.4) and `app.number-position` (`32af5da`, 89.1); variants for `added-above`, `uncertain`,
  `uncertain-strongly` (`05bc744`). Reconcile flags explained: dot rows at the zone centre (most flags), dots of area < 6, letter pieces in
  the x-height band (086.2–5, 086.22, 086.30), ϥ/ⲣ dots below the zone window, margin numerals, the "(?)" point (089.12). Caught before commit:
  086.2 a ⲙⲛ stroke written against its measurement and 090.4 a dropped ⲁ (both by the print preview; §3.36–37), 090.11 a dot written under
  ⲧ (reconcile). Dotted ϣ accepted after 8× comparison: 088.9, 089.23; none on 086, 087, 090. Kephalaion 32 ends 086.17, 33 ends 086.30,
  34 ends 087.13, 35 ends 087.29, 36 ends 088.33, 37 ends 089.17, none with an end sign; 33 opens 86.18, 34 opens 86.31, 35 opens 87.14,
  36 opens 87.30, 37 opens 89.1, 38 opens 89.18. Method §3 items 36–37; decisions §4 (2026-11-25). No new sign types (one more block, 88.21;
  one more apostrophe, 90.4). No pages skipped.

- **2026-11-26** — Routine run: read 091–095 on `reading/2026-11-26`. All five validate "ok"; all 95 pages re-validated after each vocabulary change
  (`41ab7ed`, `5f50928`, `afbcf57`: new id `app.original-reading`; variants for page-condition, added-above, expunged, sic). Reconcile flags explained:
  dot rows at the zone centre and pale dots of area < 6 (091.10/12/21/33, 092.10/25, 095.5/10–13), dots below the zone window (093.24, 095.18), letter
  feet and bracket feet (095.3/11/16), a dot under a restored letter (094.11). Caught before commit: 092.14 ϣ → ⲥ (print preview), 092.27 ϭⲱⲱ̣ⲛⲧ (8×),
  095.23 a line-end "block" that is a smudged ⲛ (print preview, pixel rows). Dotted ϣ accepted after 8× comparison: 091.4, 092.25, 093.10, 093.24; none
  on 094, 095. Kephalaion 38 (opened 89.18) runs through all five pages; sections open in ekthesis or after "leer" with enlarged letters. Method §3
  items 38–40; decisions §4 (2026-11-26). No new sign types (one more block, 93.30). No pages skipped.

- **2026-11-27** — Routine run: read 096–100 on `reading/2026-11-27`. All five validate "ok"; all 100 pages re-validated after each vocabulary change (`ec6ed70`
  "Es müßte lauten" → `conjecture`; `82f0548` "Über … etwas übergeschrieben" → `added-above`; ids unchanged). Reconcile flags explained: dot rows at the zone
  centre (096.11, 097.11, 098.12/22, 099.33), dots of area < 6 (096.6, 097.10), dots cut by the lower edge of the window (099.18, 100.23), a dotted ϣ's bowl dot
  (099.12), a broken letter foot counted as a dot (099.28), dots under restored or bracket-adjacent letters (097.7/9/15/16/33/34). Caught before commit: 100.31
  a ⲧ read from the orientation sheet that the page does not print (6×; §3.41), 097.4 a stroke first put on the wrong ⲙⲡⲥⲉϫⲉ (pixel rows). Dotted ϣ accepted after
  8× comparison: 096.17, 097.6, 097.10, 097.26, 099.10, 099.12; none on 098, 100. Kephalaion 38 (opened 89.18) runs through all five pages; sections open in ekthesis,
  after "leer" or after unmarked blanks with enlarged letters. Method §3 items 41–43; decisions §4 (2026-11-27). No new sign types (one more block, 98.23; one more
  middle dot, 96.25). No pages skipped.

- **2026-11-28** — Routine run: read 101–105 on `reading/2026-11-28`. All five validate "ok"; all 105 pages re-validated after each vocabulary change (`47e11e0`
  "leer" inside a restoration → `blank-probable`; `60d3310` "kleiner geschrieben, wohl nachgetragen" → `written-small`; `7b147ed` new id `app.ligature`). Reconcile flags
  explained: dot rows at the zone centre (101.34, 103.13, 104.14, 105.34), dots of area < 6 or below the ink threshold (102.34, 103.11/12, 105.29), dots right of a ⲣ
  descender below the window (101.14), a dot joined to ϩ (104.10), a dotted ϣ's bowl dot (101.17), letter and bracket feet (102.30, 103.6, 104.26/28), margin numerals
  and title ornaments (102.14, 104.22, 105.16/17), the colon (102.12, 103.33). Notes of 101–102 completed with the flag explanations in a separate commit (`e6bc94f`, notes
  only). Caught before commit: the reading of the 103.21 footnote written without its stroke (preview; §3.44). Dotted ϣ accepted after 8× comparison: 101.17, 102.16,
  103.24, 104.8; none on 105. Kephalaion 38 ends 102.12 with `:—`; 39 opens 102.13 and ends 104.20 ("leer"); 40 opens 104.21 and ends 105.14 (ⲛ[ⲛⲁ]ⲛⲏϩⲉ + "leer");
  41 opens 105.15. Method §3 items 44–45; decisions §4 (2026-11-28). No new sign types (two more blocks, 101.9, 101.30; one more colon, 103.33; one more apostrophe,
  103.4; one more `:—`, 102.12). No pages skipped.

---

## 7. Signs and patterns to study

Marks the reading encodes but does not yet understand. The aim is to collect occurrences until a pattern shows; do not
guess a meaning before then. `python signs.py` lists every occurrence (page.line, neighbouring words, line end, end of
kephalaion, preceding blank). After each session, update the counts below and write down any pattern the list now
shows, with the occurrences that support it.

| Type | Draft | Occurrences (2026-11-21) | What the occurrences show so far |
|---|---|---|---|
| middot | `·` | 10.34, 29.26, 32.9, 40.26, 51.14, 52.12, 52.19, 61.20, 63.25, 71.9, 77.31, 96.25, 159.33 | mid-line between words (11×; 96.25 a large round point between two parallel clauses ϣⲁϥⲙⲁⲣⲟⲩ · ϣⲁϥⲥⲙⲛ̄, 20 px spaces on both sides; 77.31 a small point, area 6, between ⲛⲛϣⲏⲣⲉ and ⲙ̄ⲡⲧⲏⲩ, "the sons of the wind"; 71.9 a large round point between ⲉϥ and ⲡ̣ on a damaged line; 61.20 and 63.25 large round dots between clauses; 40.26, 51.14, 52.12 large round dots, area 32–44); 52.19 after ϣⲁⲁⲛⲏϩⲉ before "leer", mid-kephalaion; once at a line and kephalaion end (159.33) |
| colon | `⁚` | 30.11, 36.26, 103.33 | 30.11, 36.26 at the end of a kephalaion, after the last word, no dash (contrast the end mark `:—`); 103.33 after ⲛ]ⲉ before "leer" at a section end inside kephalaion 39 (signs.py marks it as a kephalaion end only because it is the last line of the page) |
| point | `∙` | 34.12 | end of a kephalaion, after a word space |
| block | `▪` | 31.28, 33.20, 68.4, 73.3, 75.8, 83.5, 88.21, 93.30, 98.23, 101.9, 101.30 | 101.9 at a line start before ϩⲙ and 101.30 at a line end after ⲁⲛⲁⲕ (24 px space), both grey boxes with a darker left side, both where the sense calls for ⲉ (ⲟⲩ|ⲉ ϩⲙ ⲡⲕⲟⲥⲙⲟⲥ; ⲁⲛⲁⲕ ⲉ|[ⲧⲁⲓ]ⲉⲓⲣⲉ) — the block may stand for a letter the printer could not set or the editors could not read; 31.28, 33.20, 83.5 (after ⲁϫⲱϥ, a 22 px blank), 88.21 (after ⲧϩⲣⲧⲉ, a 30 px blank), 93.30 (after ⲉⲧⲙ̄ⲙⲉⲩ, a 20 px space, at a section end inside kephalaion 38) at a line end, mid-kephalaion; 68.4 and 75.8 inside a row of illegible dots where a dot would stand, before a word (ⲙⲙⲁϥ, ⲡⲣⲱⲙⲉ); 73.3 at a line start before [ⲙ]ⲡⲥⲏⲩ, after a section-ending line; 98.23 at a line start before ⲁⲛ (frame darker than the centre, 13 px), mid-sentence; three of five stand on damaged lines next to lost text; may be a printing mark, not the manuscript's |
| cross | `†` | 39.19 | line end after a 64 px blank, mid-kephalaion (9) |
| high-point | `˙` | 58.29 | once, right after ⲩ of ⲛⲉⲩ before ⲁⲃⲁⲗ, mid-kephalaion, at the top of the x-height |
| apostrophe | `ʼ` | 27.1, 52.20, 54.10, 62.28, 76.9, 90.4, 103.4 | 103.4 after the final ⲧ of ⲛⲁϩⲙⲉⲥⲧ before ⲁⲛⲟⲩⲑⲣⲟⲛⲟⲥ, a raised comma (as 90.4: twice after a word-final ⲧ before a word beginning with ⲁ); 90.4 after the final ⲧ of ⲛ̄ⲕⲧⲟⲩⲛⲟⲩⲓ̈ⲉⲧ before ⲁⲃⲁⲗ, a raised comma; after a letter at a word end or inside a word: after ⲧ (27.1, 52.20 ⲙⲡⲙⲁϩϣⲁⲙⲧʼ), after ϩ inside a restoration (54.10 [ϩʼⲣⲉⲧⲟⲩ], a thick raised stroke), after ⲡ before a restoration (62.28 ⲡ[ʼⲣⲏⲧⲉ]) — twice before ⲣ; 76.9 inside a run of lost dots after ⲉⲧⲁ[, so the letter before it is lost |
| loop-mark | `∾` | 62.27 | once, at the right edge of a line after ⲛⲧⲉϥϭⲓⲛⲉⲓ, mid-kephalaion (19), on a heavily damaged page |
| dicolon-dash | `§` | 64.1, 102.12, 183.9 | 183.9 and 102.12 (after ⲉⲧⲁⲕⲧⲉⲟⲩⲁϥ ⲁⲣⲁⲛ, end of kephalaion 38) at a kephalaion end; 64.1 mid-kephalaion (20), before a section opening with an enlarged ⲡ (ⲡⲁⲗⲓⲛ) |

Kephalaia 9, 10 and 11 end on 042.23, 043.21 and 044.18 with no printed end sign (two of the three end lines are
damaged), so far the colon/point at a chapter end is the exception, not the rule (30.11, 34.12, 36.26 against 042–044).
Kephalaia 12, 13 and 14 end on 045.15, 046.12 and 047.21 with no end sign either (045.15 and 047.21 end in "leer").
Kephalaion 16 ends on 055.15 (a line of dots + "leer") with no end sign; kephalaia 17 and 18 end on 057.32 and 060.12 in lines of
dots, so whether they carried a sign cannot be seen. Pattern so far: a mark follows "ϣⲁⲁⲛⲏϩⲉ / ⲛⲁⲛⲏϩⲉ" (for ever) at
the end of a section three times — 30.11 colon (kephalaion end), 34.12 point (kephalaion end), 52.19 middle dot (section end before
"leer", mid-kephalaion); sections ending in "leer" without that formula carry none (50.22, 51.17, 53.17, 53.27, 54.9).

Kephalaia 19, 20 and 21 end on 063.18 (dots), 064.12 ("leer") and 065.13 with no end sign; 065.13 ends in ϣⲁ ⲁⲛⲏϩⲉ + "leer" and has
no mark, so the "ϣⲁⲁⲛⲏϩⲉ + mark" pattern above holds three times out of four. The end mark `:—` stands once at a section break
inside a kephalaion (64.1), so it is not only a chapter-end sign.

Kephalaia 22 and 23 end on 066.27 (a line of dots) and 070.7 (dots + "leer") with no end sign; whether 066.27 had one cannot be seen.
New sections inside kephalaion 23 open after "leer" with an enlarged letter in the same line (67.3 Ⲡⲉⲧⲉ, 67.16 Ϩⲁⲡⲣⲁ, 68.10 Ⲧⲟⲧⲉ) or
in ekthesis (67.23, 68.29, 69.7), and twice without an enlarged letter (69.16, 69.19 ⲙⲡⲥⲏⲩ ⲇⲉ ϩⲱⲱϥ); none carries a sign.

Kephalaion 24 (opened 70.8) runs through 071–075 without an end. Its sections open after "leer" with an enlarged letter on the same line
(71.3 Ⲧⲉⲓ, 71.4 Ⲧϩⲉ, 74.9 Ⲁⲗⲗⲁ, 75.3 [Ⲧⲉ], 75.16 Ⲡⲙⲁϩϣⲁⲙⲧ) or in ekthesis (71.19, 72.7, 72.28, 74.7, 75.13/20/24/32); 075 lists the
fathers as "the second … the third … the fourth … the fifth … the sixth" (ⲡⲙⲁϩⲥⲛⲉⲩ, ⲡⲙⲁϩϣⲁⲙⲧ, ⲡⲙⲁϩϥⲧⲁⲩ, ⲡⲙⲁϩϯⲟⲩ, ⲡⲙⲁϩⲥ[ⲁⲩ]) with an enlarged Ⲡ each time. None of these breaks carries a sign.

Kephalaia 24–27 end on 076.14 ("leer"), 076.25 (ϩⲙ̄ ⲡⲉϥⲕⲁⲓⲣⲟⲥ, the numeral follows), 077.21 (ϩⲙ ⲡⲙⲁⲛⲣⲉϣⲉ) and 079.12 ([ϣⲁ] ⲁⲛⲏϩⲉ + "leer")
with no end sign. 079.12 and 076.3 (ⲟⲩϣⲁⲁⲛⲏϩⲉ ⲧⲉ + "leer", a section end) are two more ϣⲁⲁⲛⲏϩⲉ endings without a mark, so the "ϣⲁⲁⲛⲏϩⲉ +
mark" pattern now holds three times out of six (30.11, 34.12, 52.19 against 65.13, 76.3, 79.12). Kephalaion 28 (the twelve judges) on 079–080
opens each judge with an enlarged Ⲡ (Ⲡⲙⲁϩ-…), in ekthesis (79.16, 79.23, 79.26, 79.29, 80.5) or in the line after "leer" (79.33, 80.9, 80.18,
80.25, 80.29), once at the line start without ekthesis (80.33); no break carries a sign.

Kephalaia 28–31 end on 081.20 (ϣⲁ ⲁⲛⲏϩⲉ + "leer"), 083.16 ("leer"), 084.4 and 085.18 (both the last word, no "leer") with no end sign:
the "ϣⲁⲁⲛⲏϩⲉ + mark" pattern now holds three times out of seven. In kephalaion 29 (the nine thrones, 081–083) and 32 (085) sections open with
an enlarged letter in ekthesis or after "leer", and also after an unmarked blank with an ordinary ⲡ (83.4, 83.8, 85.29); none carries a sign.

Kephalaia 32–37 end on 086.17, 086.30, 087.13 (all "leer"), 087.29 (the last word, no "leer"), 088.33 (ⲛ̄ϩⲏⲧϥ + "leer") and 089.17 ("leer") with no
end sign. On 088.34 a lone numeral ⲗⲋ is printed under the end of a section of kephalaion 36 with no title; its function is not clear (a repeated
chapter number before the next section?). Sections in 086–090 open with an enlarged letter in ekthesis or after "leer", or with an ordinary ⲡ
after "leer" (87.11, 89.31, 89.34); none carries a sign.

Kephalaion 38 (opened 89.18) runs through 090–095 without an end. Its sections open in ekthesis with an enlarged letter (92.1, 92.5, 92.7, 92.12, 92.24,
93.9, 93.16, 93.20, 93.29, 94.1, 94.17, 94.28), in the line after "leer" with an enlarged letter (94.6, 94.11, 94.22, 92.32 Ⲡⲁⲇⲁⲙⲁⲥ), after an unmarked
blank (94.33, 95.7), once in mid-line after an ordinary space (93.10) and once after "leer" without an enlarged letter (93.23). One break carries a block
(93.30, at a line end before [ⲧⲁϥ]ϣⲱⲡⲉ); the rest carry no sign.

Kephalaion 38 runs on through 096–100. Its sections open in ekthesis with an enlarged letter (96.22, 100.1, 100.15, 100.19, 99.30 restored Ⲛ̄), with an
ordinary ϯ in ekthesis (100.23), after "leer" with an enlarged letter on the same line (97.26, 98.15, 100.6) and after an unmarked blank of 49–77 px with an enlarged
Ⲉ, Ⲧ or restored Ⲡ (97.8, 99.2, 99.22, 99.23, 99.27, 100.11), twice in mid-line after an ordinary space (97.7, 97.21); none carries a sign.

Kephalaion 38 ends on 102.12 with the end mark `:—`, the second `:—` at a kephalaion end (183.9) and the first in this run of pages. Kephalaion 39 ends on 104.20 and
40 on 105.14 (ⲛ[ⲛⲁ]ⲛⲏϩⲉ + "leer") with no end sign; the "ϣⲁⲁⲛⲏϩⲉ + mark" pattern now holds three times out of eight (105.14 without a mark), and the section ends
102.3 (ϣⲁ ⲁⲛⲏϩⲉ + "leer") and 105.35 (ⲛ]ⲁⲛⲏϩⲉ + "leer") carry none either. 103.33 is a section end with a colon before "leer" (after ⲛⲉⲓ ⲛ]ⲉ, "these are they"),
the first colon not at a kephalaion end. Sections in 101–105 open in ekthesis with an enlarged or restored enlarged letter, after "leer" with an enlarged letter in the
same line (101.8, 102.19, 102.28, 103.10, 104.6, 105.1, 105.21, 105.24), after "leer" with an ordinary ⲡ (101.13, 103.2, 103.7), and in mid-line with an enlarged letter
after an ordinary space (101.31 Ⲙⲟⲩϩ, 105.32 Ⲡϩⲁⲩⲧ, 105.33 Ⲥⲉⲛⲁⲡⲁϣϥ); none carries a sign.

Open questions: Are colon and point two forms of one chapter-end sign? Does the cross recur at section breaks? Are the
blocks the printer's or the editors'? Do the middle dots separate units of sense?

**About the printed Coptic (user observation, 2026-11-15).** The Coptic of this edition appears to be hand-drawn with
letter templates (stencils), not set in metal type. This explains why overlines vary in length and position (35.13 bar
displaced onto ⲡⲉ; strokes near the 50 % mark on ⲙⲛ, ϩⲛ, ⲛⲛ) and why some strokes and dots look blurred. Decision:
the ≥ 50 % rule stays, because it keeps the encoding the same on every page, and every measured percentage stays in
the `print` notes so that the borderline cases (45–55 %) can be re-judged together later. Shapes that vary between
copies of one letter (ϯ 17 px wide, the 39.19 cross 23 px) are compared on the same page.
