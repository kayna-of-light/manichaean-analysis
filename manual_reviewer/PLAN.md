# Manual Reviewer — Plan

A Next.js webapp for line-by-line, character-by-character manual correction of the
Kephalaia OCR output. The aim is to lock in the best of `kephalaia_ocr` (good base
recognition, clusters, geometry, candidate lists) with a tight human-in-the-loop
correction surface, instead of pushing the unsupervised pipeline further.

This document is the **single source of truth** for scope, progress, and decisions.
Update checkboxes as items land. Add dated entries to the "Decisions log" at the
bottom when scope changes.

---

## 0. Data sources (read-only; do not mutate)

All inputs come from the canonical pipeline output. The reviewer never writes back
into these:

| Path | Role |
|---|---|
| `output/projects/kephalaia_ocr/pages/keph_p{NNN}_body.jpg` | Body-cropped page image |
| `output/projects/kephalaia_ocr/pages/keph_p{NNN}_body_bbox.json` | Body crop offset in the original page |
| `output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected/keph_p{NNN}_lines_base_split.json` | Lines + blobs with both `warped_bbox` (line-space) and `img_quad` (page-space) |
| `output/projects/kephalaia_ocr/contextual_review/clusters_shape_padded_split_bodycrop_corrected_k240/line_sequences.jsonl` | Per-line ordered tokens with `cluster`, `label`, `candidates`, `manual_override`, `geometric_override`, `review` flag, geometry |
| `output/projects/kephalaia_ocr/clusters_shape_padded_split_bodycrop_corrected_k240/c_{CCC}_n{NNNN}.png` | Cluster representative thumbnails |
| `output/projects/kephalaia_ocr/clusters_shape_padded_split_bodycrop_corrected_k240/_assignments.json` | All blob→cluster assignments (large, >50 MB; load via streaming or per-page index) |
| `output/projects/kephalaia_ocr/clusters_shape_padded_split_bodycrop_corrected_k240/subclusters/` | Cluster member listings |

---

## 1. Writeback model (SQLite, transactional)

**All edits land in a single SQLite database** at `manual_reviewer/data/reviewer.db`.
Nothing in `output/projects/kephalaia_ocr/` is ever modified. SQLite is chosen over
JSON sidecars because it gives us:

- **ACID writes** — every edit is a transaction; a crash mid-write cannot corrupt state.
- **WAL mode** — concurrent reads while a write is in flight; no half-written files.
- **Append-only audit log as a table**, easy to query and replay.
- **Cross-edit queries** ("all blobs in cluster 82 currently overridden") in milliseconds.
- **Single-file backup** — the whole project state is one file we can copy.

Stack: `better-sqlite3` (synchronous, very fast, perfect for a single-process
Next.js dev server). On boot we run idempotent `CREATE TABLE IF NOT EXISTS` migrations.

```
manual_reviewer/data/
  reviewer.db              # primary store (WAL: reviewer.db-wal, reviewer.db-shm)
  backups/
    reviewer-YYYYMMDD-HHMM.db   # nightly + on-demand snapshots
  exports/                 # pipeline-compatible JSON exports generated on demand
```

### Schema (v1)

```sql
-- One row per page reviewed (created lazily on first edit).
CREATE TABLE IF NOT EXISTS pages (
  page TEXT PRIMARY KEY,                -- "100"
  status TEXT NOT NULL DEFAULT 'pending', -- pending | in_progress | done
  last_edited_at TEXT
);

-- Per-line status, note, and free-form metadata.
CREATE TABLE IF NOT EXISTS lines (
  page TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', -- pending | in_progress | done | flagged
  note TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (page, line_index)
);

-- Edits to existing pipeline blobs.
-- (page, line_index, blob_id) uniquely identifies a pipeline blob.
CREATE TABLE IF NOT EXISTS blob_edits (
  page TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  blob_id INTEGER NOT NULL,
  label TEXT,                            -- base char, or special marker (_lacuna_dot etc.)
  diacritics TEXT NOT NULL DEFAULT '[]', -- JSON array: ["overline", "dot_above", ...]
  lacuna_bracket TEXT,                   -- 'left' | 'right' | null
  deleted INTEGER NOT NULL DEFAULT 0,    -- 0 | 1
  source TEXT NOT NULL,                  -- manual | candidate | cluster
  updated_at TEXT NOT NULL,
  PRIMARY KEY (page, line_index, blob_id)
);
CREATE INDEX IF NOT EXISTS idx_blob_edits_page ON blob_edits(page);

-- New bboxes drawn by the reviewer (id is app-generated string).
CREATE TABLE IF NOT EXISTS new_bboxes (
  id TEXT PRIMARY KEY,                   -- "new_p100_l16_0001"
  page TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  x0 REAL NOT NULL, y0 REAL NOT NULL,
  x1 REAL NOT NULL, y1 REAL NOT NULL,
  coord_space TEXT NOT NULL,             -- 'warped' | 'image'
  label TEXT,
  diacritics TEXT NOT NULL DEFAULT '[]',
  lacuna_bracket TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_new_bboxes_page_line ON new_bboxes(page, line_index);

-- Cluster-wide label overrides. Applied at read time except where a blob has a manual edit.
CREATE TABLE IF NOT EXISTS cluster_overrides (
  cluster_id TEXT PRIMARY KEY,           -- "082"
  label TEXT NOT NULL,
  diacritics TEXT NOT NULL DEFAULT '[]',
  note TEXT,
  applied_at TEXT NOT NULL
);

-- Blobs explicitly removed from their cluster ("global unset" space).
CREATE TABLE IF NOT EXISTS unset_blobs (
  page TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  blob_id INTEGER NOT NULL,
  removed_from_cluster TEXT,
  moved_at TEXT NOT NULL,
  PRIMARY KEY (page, line_index, blob_id)
);

-- Global tasks / flags on lines.
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  page TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  kind TEXT NOT NULL,                    -- revisit | needs_specialist | ambiguous
  note TEXT,
  resolved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_open ON tasks(resolved, page, line_index);

-- Append-only audit log: every state-mutating action.
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  action TEXT NOT NULL,                  -- 'blob_edit' | 'blob_delete' | 'bbox_create' | ...
  page TEXT,
  line_index INTEGER,
  target_id TEXT,                        -- blob_id or new_bbox id, as string
  before TEXT,                           -- JSON snapshot, may be null
  after TEXT                             -- JSON snapshot, may be null
);
CREATE INDEX IF NOT EXISTS idx_audit_page ON audit_log(page, line_index, at);

-- Single-row schema version table.
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1');
```

### Durability rules

- WAL mode (`PRAGMA journal_mode=WAL`), `PRAGMA synchronous=NORMAL` (safe with WAL).
- Every API mutation runs inside a single `BEGIN IMMEDIATE` transaction that also writes
  the `audit_log` row, so an edit and its audit entry are atomic.
- Auto-backup on startup if the previous backup is >24h old.
- Manual `POST /api/backup` endpoint that copies the db to `data/backups/` using the
  SQLite online backup API (safe while the app is running).
- Export to pipeline-compatible JSON is read-only over the db; it never moves the
  source of truth out of SQLite.

---

## 2. Application architecture

### Stack

| Layer | Choice |
|---|---|
| Framework | Next.js 15 (App Router, React 19, TypeScript, ESM) |
| Styling | Tailwind CSS v4 + MUI v6 (sx + Tailwind side by side) |
| Theme | Glass-morphism custom theme provider (light + dark modes, frosted surfaces, subtle gradients) |
| State | Zustand for client state; React Query for server fetches |
| Validation | Zod schemas shared between API routes and client |
| Persistence | SQLite via `better-sqlite3`; WAL mode; transactional writes; auto-backups |
| Images | Local file serving via `/api/image` route, no `next/image` optimization (preserves pixel accuracy) |
| Drawing | HTML canvas overlay on top of the line/page image; pointer events; no external lib for v1 |
| Coptic input | Latin-mapped keyboard layer (see §3.5) with modifier combos for diacritics/brackets; on-screen picker as fallback |

### Directory layout

```
manual_reviewer/
  PLAN.md                       # this file
  README.md                     # how to run, dev notes
  package.json
  next.config.mjs
  tailwind.config.ts
  tsconfig.json
  postcss.config.mjs
  src/
    app/
      layout.tsx
      page.tsx                  # landing / page picker
      review/[page]/page.tsx    # per-page reviewer
      api/
        pages/route.ts          # list available pages
        page/[id]/route.ts      # consolidated page data (image url + lines + tokens + edits)
        edits/[page]/route.ts   # GET / PUT page edits
        cluster/route.ts        # GET / PUT cluster overrides
        cluster/[id]/members/route.ts
        cluster/[id]/unset/route.ts
        tasks/route.ts
        image/route.ts          # secure file proxy (whitelisted roots)
        export/route.ts         # produce pipeline-compatible exports
    components/
      theme/                    # ThemeProvider, glass surfaces
      layout/                   # AppShell, TopBar, PageNav
      reviewer/
        LineCanvas.tsx          # image + bbox overlay
        TokenStrip.tsx          # predicted char row (like page_review_sheets)
        CharChooser.tsx         # base + diacritics picker
        BboxDrawer.tsx          # add new bbox
        ClusterPanel.tsx        # right-side panel for cluster ops
        ClusterMemberGrid.tsx   # cluster thumbnails, multiselect
        TaskFlagButton.tsx
        UndoRedo.tsx
        ProgressBar.tsx
      shortcuts/
        useKeyboardShortcuts.ts
    lib/
      paths.ts                  # absolute paths, env config
      pipelineReaders.ts        # read pages / line_sequences / clusters (read-only, cached)
      db.ts                     # better-sqlite3 connection, migrations, prepared statements
      repo.ts                   # high-level query / mutation helpers (always wrap audit)
      coordTransform.ts         # warped<->image<->client transforms
      copticInventory.ts        # the full base char set + diacritic options
      copticKeymap.ts           # Latin → Coptic + modifier mappings (see §3.5)
      zodSchemas.ts
    styles/
      globals.css               # Tailwind + glass tokens
  data/                         # gitignored; SQLite db + backups + exports
    reviewer.db                 # primary store
    backups/
    exports/
  scripts/
    build_page_index.ts         # precompute per-page slices of line_sequences.jsonl into a fast index
```

### Coordinate transforms

The line tokens carry two boxes per blob:
- `warped_bbox` is in line space (the rectified strip used during OCR).
- `img_quad` is the four corners of the same region projected back into the body-cropped image.

For v1 we render directly on the body image using `img_quad`. A toggle later can show the rectified line strip instead. All editing happens visually in image space; for storage we keep `warped_bbox` as the canonical coordinate so it remains compatible with the python pipeline, and we maintain a `img_quad` for any newly drawn boxes (computed via the line's warp transform when available; otherwise we store a flat axis-aligned quad in image space).

---

## 3. UI design

### Theme: glass

- Background: deep manuscript-paper gradient (warm dark in dark mode, parchment in light mode).
- Surfaces: `backdrop-filter: blur(20px) saturate(140%)` on top of a 6% white/black layer; 1px hairline border at 12% opacity; soft shadow with low-opacity drop and large blur.
- Typography: a humanist sans (Inter) for UI; a Coptic-capable serif (Noto Sans Coptic / Antinoou) for character displays.
- Accent: gold (#C8A465) for action affordances; muted teal for selection.
- Motion: 180ms ease-out on hover / focus; spring on chooser open.

### Per-page reviewer layout

```
+----------------------------------------------------------------+
| Top bar: page picker · progress · save status · keymap help    |
+------------------+---------------------------------------------+
| Line list (L)    | Image area (top): line strip + bbox overlay |
|  ☐ 16 ●          |                                             |
|  ☐ 17            +---------------------------------------------+
|  ☑ 18 done       | Token strip (bottom): predicted chars,      |
|  ⚑ 19 flagged    | click to edit, badge if differs from OCR    |
|  …               |                                             |
|                  +---------------------------------------------+
|                  | Inline char chooser (popover) when a token  |
|                  | is selected (base grid + diacritics)        |
+------------------+---------------------------------------------+
| Bottom drawer: cluster panel · global tasks · audit log        |
+----------------------------------------------------------------+
```

### Interactions (must-haves)

1. **Click a predicted character** → opens the char chooser anchored to the bbox.
   - Coptic base grid (lowercase, by frequency, with search).
   - Diacritic toggles: overline, underline, dot above, dot below, supralinear stroke.
   - "Use candidate" shortcut row showing the existing `candidates[]` and `alt` from the pipeline (one-click apply).
   - Mark as lacuna dot / square bracket / curly bracket via dedicated icons.
   - Esc cancels; Enter applies.

2. **Delete a character** → trash icon in the chooser, or `Delete` key when a token is focused. Stored in `deleted_blob_ids`.

3. **Add a new bbox** → "n" key or "+ bbox" button starts drawing on the image. Pointer drag draws a rectangle clipped to the line band. On release, the char chooser opens for the new bbox.

4. **Flag a line as a global task** → "f" key or the flag button on the line row. Choose `kind` and note. Line moves to "flagged" state and an entry is added to `tasks/global_tasks.json`.

5. **Cluster reassignment** → in the cluster panel, choose a cluster, choose a new label, click "Apply to cluster". All blobs in that cluster across the entire corpus get the new label **except** blobs that already have a manual edit. Confirmation modal shows: cluster size, how many will change, how many manual edits will be respected.

6. **Cluster member browsing + multiselect delete** → cluster panel shows a paginated grid of cluster members (thumbnails from the cluster dir). Click to multiselect; "Move to unset" detaches them from the cluster and adds them to `cluster/unset/blobs.json`. Unset blobs surface as "needs assignment" in their own page views (red border).

### Nice-to-haves (in scope, after must-haves)

- **Keyboard navigation**: `j` / `k` between tokens, `J` / `K` between lines, `g g` to jump to page, `?` for cheatsheet.
- **Per-line progress bar** at the top of the page.
- **Diff badge** on each token when the user value differs from the pipeline label.
- **Hover preview**: hovering a token highlights the bbox on the image and vice versa.
- **Compare panel**: optional column showing a translation/reference line text when one is available (initially empty; user can paste reference per line).
- **Undo / redo** stack (last 100 edits in the current session).
- **Export** to `_manual_glyph_overrides.json` shaped exactly like the python pipeline expects.

### 3.5 Coptic typing layer (keyboard-first)

When a token chooser or new-bbox chooser is **focused**, the keyboard switches into
**Coptic typing mode** (visually indicated by an accent border on the chooser and a
small badge in the top bar). In this mode the standard Latin layout is remapped to
Coptic base characters, with `Shift`/`Ctrl`/`Alt` adding diacritics, brackets, and
markers. When the chooser is **not** focused, normal app shortcuts apply (`j/k`,
`f`, `n`, `d`, etc.).

**Base map** (Latin key \u2192 Coptic letter, lowercase):

| Key | Coptic | Notes |
|---|---|---|
| a | \u2c81 alpha | |
| b | \u2c83 beta | |
| g | \u2c85 gamma | |
| d | \u2c87 delta | |
| e | \u2c89 epsilon | |
| z | \u2c8d zeta | |
| h | \u2c8f eta | (Coptic \u0119 / \u0113 sound) |
| q | \u2c91 theta | |
| i | \u2c93 iota | |
| k | \u2c95 kappa | |
| l | \u2c97 lambda | |
| m | \u2c99 mu | |
| n | \u2c9b nu | |
| x | \u2c9d xi | |
| o | \u2c9f omicron | |
| p | \u2ca1 pi | |
| r | \u2ca3 rho | |
| s | \u2ca5 sigma | |
| t | \u2ca7 tau | |
| u | \u2ca9 upsilon | |
| f | \u2cab phi | |
| c | \u2cad chi | |
| y | \u2caf psi | |
| w | \u2cb1 omega | |
| j | \u03ef shei (\u03ee) \u2014 actually \u2ca5 ? \u2192 use \u03e3 | **\u03e3 shai** (Coptic) |
| J | \u03e2 | uppercase shai |
| v | \u03e5 fai | |
| V | \u03e4 | |
| F | \u03e7 hori | (\u03e6 uppercase) |
| H | \u03e6 | |
| D | \u03e9 dei | (\u03e8 uppercase) for Sahidic \u03e9 (Bohairic letter) |
| G | \u03eb gangia | |
| Q | \u03ed kjima | |
| Y | \u03ef ti | |

(The exact letter\u2192symbol assignments will be tuned with the user; the principle is\n\"phonetic where possible, mnemonic where not\". Final table lives in\n`src/lib/copticKeymap.ts` and is editable.)\n\n**Modifier overlays** (additive; combine freely):\n\n| Combo | Effect |\n|---|---|\n| `Shift` + key | Uppercase form of the same Coptic letter |\n| `Alt` + key | Add **overline** (supralinear stroke) to the just-typed character |\n| `Alt+Shift` + key | Add **underline** |\n| `Ctrl+Alt` + key | Add **dot above** |\n| `Ctrl+Alt+Shift` + key | Add **dot below** |\n\n**Special-marker keys** (chooser mode only):\n\n| Key | Marker |\n|---|---|\n| `[` | open Leiden bracket `_left_square_bracket` |\n| `]` | close Leiden bracket `_right_square_bracket` |\n| `(` | open round bracket |\n| `)` | close round bracket |\n| `.` | lacuna dot `_lacuna_dot` |\n| `?` | `_unknown` |\n| `\\` | `_connected_needs_literal_reading` |\n| `Backspace` | clear current label |\n| `Enter` | commit and advance to next token |\n| `Escape` | cancel without applying |\n| `Tab` | commit and stay on current token |\n\n**Visual feedback**: while the chooser is focused, an overlay strip at the bottom\nof the chooser shows live decoding: \"`alt + i` \u2192 \u2c93 + overline \u2192 \u2c93\u0305\". A small\n\"keymap\" button opens the full reference table.\n\n**Editability**: the keymap is a single TypeScript object so the user can adjust\nbindings; we ship a sensible default and let it be tweaked without a rebuild via a\n`copticKeymap.local.json` override loaded at runtime.\n\n### Explicitly out of scope for v1

- Authentication / multi-user collaboration.
- Mobile / tablet layouts.
- Direct edits to pipeline outputs.
- Automatic re-OCR after edits (we only collect overrides; re-OCR is offline).

---

## 4. Phased delivery (trackable)

Use this as the running checklist. Tick boxes as items ship.

### Phase 0 — Plan & decisions
- [x] Inventory inputs and confirm data shape
- [x] Sketch sidecar schemas
- [x] Choose stack (Next.js + MUI + Tailwind + glass theme)
- [x] Write this `PLAN.md`

### Phase 1 — Scaffold
- [x] `pnpm` Next.js 16 (TS, App Router, Tailwind v4) project under `manual_reviewer/`
- [x] Add MUI v9 + Emotion; integrate with Tailwind (Tailwind v4 has no preflight clash; CSS-first config)
- [x] Add Zustand, React Query, Zod, `better-sqlite3`
- [x] Glass theme provider (light + dark; toggle persisted to localStorage)
- [x] App shell: top bar, content slot (side rail comes with Phase 3 reviewer view)
- [x] `README.md` with `dev` / `build` / `start` instructions and env vars
- [x] Wire `KEPH_OUTPUT_DIR` and `KEPH_DATA_DIR` env vars (default to relative `../output/projects/kephalaia_ocr` and `./data`)
- [x] `lib/db.ts` opens / migrates `data/reviewer.db`, enables WAL, sets pragmas
- [x] Startup auto-backup if last backup > 24h old

### Phase 2 — Data layer (read)
- [x] `pipelineReaders.ts`: list pages from `pages_base_split_chars_bodycrop_corrected/`
- [x] Build per-page index of `line_sequences.jsonl` once at server start (cache in memory) — avoid loading the full JSONL on every request
- [x] `/api/pages` returns the page list with progress (counts from sidecar edits)
- [x] `/api/page/[id]` returns: image url, body bbox, lines (with tokens, candidates, overrides) merged with current sidecar edits
- [x] `/api/image` whitelisted proxy that serves files only from the two known roots
- [x] Unit-level sanity check: render a page in a barebones test view (no editing yet)

### Phase 3 — Read-only reviewer view
- [x] Landing page lists pages with progress badges
- [x] `review/[page]` renders the body image with the active line highlighted
- [x] Token strip under the image mirroring `page_review_sheets/p100_review.png` style (predicted char + tiny cluster id + confidence pip)
- [x] Hover sync between bbox and token
- [x] Line list sidebar with status pips
- [x] No editing yet; confirm rendering quality and coordinate transforms

### Phase 4 — Character editing
- [x] `CharChooser` popover (base grid, diacritics, lacuna/bracket buttons, "use candidate" row)
- [x] **Coptic typing layer** active while chooser focused (§3.5)
  - [x] `copticKeymap.ts` default map (Latin → Coptic + modifier overlays)
  - [ ] Optional `copticKeymap.local.json` runtime override
  - [x] Live decoding strip inside the chooser
  - [x] `Enter` commits + advances to next token
- [x] Click a token → choose label → `PUT /api/edits/[page]` runs a single SQL transaction (audit + write)
- [x] Delete a token (`Delete` or trash) writes `deleted=1`
- [x] Diff badge when user value ≠ pipeline label
- [x] Optimistic update + React Query invalidation
- [ ] Undo/redo using the `audit_log` table

### Phase 5 — Bbox creation
- [x] `BboxDrawer` canvas overlay with pointer drag, clipped to the line band
- [x] On release, generate synthetic id, persist to `new_bboxes`, open `CharChooser`
- [ ] Right-click an existing bbox → edit / delete
- [ ] Visual distinction for new bboxes (dashed accent border)

### Phase 6 — Line-level tasks
- [x] Flag a line → modal with `kind` + note
- [x] Persist to `tasks/global_tasks.json` and update line status
- [ ] Tasks list view under the bottom drawer (sortable by page, kind, age, resolved)
- [ ] Mark task resolved → status returns to whatever the edits say

### Phase 7 — Cluster panel
- [x] Cluster panel opens with the currently selected blob's cluster
- [x] Show top members as thumbnails (paginated)
- [x] "Reassign cluster" flow with confirmation modal (counts + manual-edit respect)
- [x] Multiselect cluster members → "Move to unset"
- [ ] Unset view: list all unset blobs across the corpus, click jumps to their page/line

### Phase 8 — Export
- [x] `/api/export` writes a snapshot under `data/exports/` mirroring `_manual_glyph_overrides.json`
- [x] Include unset-blob list and cluster overrides in the bundle
- [ ] `README.md` documents how to feed the export back into the python pipeline

### Phase 9 — Polish
- [ ] Keyboard shortcut cheatsheet (`?`)
- [ ] Auto-save status indicator with retry on failure
- [ ] Page-level progress bar + corpus-level progress on landing
- [ ] Empty / error / loading states throughout
- [ ] Accessibility pass (focus rings, ARIA, contrast in glass surfaces)

### Phase 10 — Hardening
- [ ] WAL + `BEGIN IMMEDIATE` transactions verified under contention (two tabs editing)
- [x] Crash recovery: on boot, run schema migrations and `PRAGMA integrity_check`
- [x] Auto-backup on startup if previous backup > 24h old (uses SQLite Online Backup API)
- [x] Manual `POST /api/backup` endpoint + button in the top bar
- [x] `data/` is gitignored from the parent repo's perspective

### Phase 11 — Cluster manager v2 + chooser enhancements

The cluster page was rebuilt to derive membership from the transposed v2 baseline
(commit pending). With correct membership in place we now upgrade the cluster
manager UX, unify the label-editing surface, add a cluster overview, and fix a
batch of cross-cutting UI issues (theme contrast, char preview, active-blob
filtering).

**Guiding principles**
- The cluster's membership is the **set of currently active baseline tokens** whose
  `cluster == cid`. Removed / unset / non-emitted blobs must not be counted or shown.
- The cluster label and the per-blob label are the **same kind of value**, so they
  must use the **same editor** (`CharChooser`), with diacritics suppressed for the
  cluster-label use case.
- Per-blob diacritics are the user's manual work; bulk operations on the cluster
  must never erase them. Bulk operations change the **base character** only.
- "Unassigned" is a real, addressable cluster — a sentinel id (`-1` /
  `"unassigned"`) — not an absence. Clearing a blob from a cluster means
  reassigning it to the unassigned cluster.

#### 11.1 Active-only cluster membership
- [x] `GET /api/cluster/[id]` filters out tokens that are deleted, unset, or
      otherwise hidden from the page reviewer (single source of truth =
      `readInitialBaseline` + edits + `unset_blobs`).
- [x] Add a `Cluster.active_total` field separate from `original_total` (raw
      assignment count) so the UI shows real counts.
- [x] Verify on a few clusters that `active_total` equals the count of crops
      visible on the corresponding pages.
- [x] Unassigned cluster: introduce sentinel id `-1` (label "Unassigned"). The API
      treats it as a normal cluster but its members are blobs whose
      `cluster_reassignments.to_cluster = -1` (or original cluster was missing).

#### 11.2 Cluster label editor = `CharChooser`
- [x] Instead of mutating `CharChooser` (deeply coupled to the reviewer's
      mutation pipeline), introduce a standalone `CopticPicker` that mirrors the
      chooser's visual layout (Coptic keyboard + specials) but with diacritics
      and bracket markers suppressed.
- [x] Replace the cluster page's text input + "Apply" with a button that opens
      `ClusterLabelDialog` wrapping `CopticPicker`.
- [x] Apply writes through the existing `apply_label` action (cluster override).
- [x] Clear override remains, relabeled "Remove cluster label".

#### 11.3 Multiselect UX (shift + ctrl/cmd)
- [x] Track `selection: Set<string>` and `anchorId: string | null` in the cluster
      page client.
- [x] Plain click → select only this blob, set anchor.
- [x] Ctrl/Cmd + click → toggle this blob in selection, set anchor.
- [x] Shift + click → select contiguous range from anchor (in current grid
      order) **without** clearing existing selection, anchor unchanged.
- [x] Ctrl/Cmd + A → select all currently rendered members.
- [x] Esc → clear selection.
- [x] Selection toolbar shows `N selected of M`, plus per-action buttons; buttons
      are disabled with a tooltip when `N == 0`.
- [x] Visual: selected crops get a strong accent border + subtle background tint
      that is readable in both light and dark theme.

#### 11.4 Selection action buttons — clear names, clear behaviour
Replace the current vague labels with explicit, verb-first names. Each shows a
confirm dialog summarising what it will do.

- [x] **"Move selection to another cluster…"** — explicit target field, tooltips.
- [x] **"Clear selection from this cluster"** — reassigns to sentinel `-1`,
      drops cluster-derived labels, preserves per-blob manual edits and
      diacritics.
- [x] **"Create new cluster from selection…"** — opens `NewClusterDialog`
      (see 11.6).
- [x] **"Undo reassignments for selection"** — surfaced with count.
- [x] **"Mark as not-a-character"** — renamed from "Unset N".
- [x] Buttons disable themselves (with tooltip) when no selection.

#### 11.5 Cluster overview page
- [x] New `GET /api/clusters` returns active counts, override labels, and a
      sample member crop per cluster.
- [x] `ClustersOverview` component renders one card per cluster with id, label,
      active count, sample crop, baseline count.
- [x] Card click → `/cluster/[id]`.
- [x] Sort: by id / by active count desc / by active count asc / by label.
- [x] Filter: non-empty / all / has label / missing label / unassigned.
- [x] Search by id or label substring.
- [x] Pagination (60 per page).

#### 11.6 Create-new-cluster flow
- [x] Action available from any cluster page when selection ≥ 1.
- [x] `NewClusterDialog` wraps `CopticPicker` with a `Skip (no label)` action.
- [x] `POST /api/clusters { action: "create_from_selection" }` allocates the
      lowest free positive id beyond the current max (taking baseline,
      overrides, and reassignments into account), records an override if a
      label was picked, reassigns the selected blobs.
- [x] Per-blob diacritics: preserved by design (overrides only set the base
      label; `mergeTokens` applies them to the *effective* cluster id).
- [x] Redirect to the new cluster's page after creation.
- [x] User-created cluster ids reuse the existing `cluster_overrides` table —
      `applyClusterOverride` accepts any integer id, so no schema change.

#### 11.7 Home navigation: Pages | Clusters
- [x] Home page rebuilt around a `Tabs` switcher: **Pages** (old grid extracted
      into `PagesOverview`) | **Clusters** (`ClustersOverview`).
- [x] Selection persisted in `localStorage` so reloads keep the user's last view.

#### 11.8 Theme audit (light + dark contrast)
- [x] Theme palette: replaced `oklch()` text colors with `rgb()` so MUI 9 can
      compute `*Channel` tokens. This eliminates the runtime warnings that
      silently muted button colors (faint outlined buttons in dark mode are
      now properly rendered).
- [x] Selection toolbar, member captions, cluster overview cards, home tabs all
      use palette tokens (`text.primary`, `text.secondary`, `text.disabled`,
      `var(--color-glass-*)`) that flip per theme.
- [x] Visual smoke pass on `/cluster/46` and `/` (Clusters tab) in dark mode.

#### 11.9 Char preview in `CharChooser`
- [x] `ChooserAnchor` gained an optional `preview: { imageUrl, imageSize, aabb }`.
- [x] The three `openChooser(...)` call sites in `app/review/[page]/page.tsx`
      (token, new-bbox, pending-new-bbox auto-open) populate `preview` from
      `data.image_url` + `data.image_size` + computed aabb.
- [x] New `ChooserPreview` component renders the crop with a one-step zoom
      toggle (fit vs. context, padded by the glyph's own height).
- [x] Wired into both `CharChooser` (token mode) and `CopticPicker` (cluster
      label + new-cluster dialogs).

#### 11.10 Sequencing
Implementation order (each step independently mergeable):

1. 11.1 active-only membership + unassigned sentinel (foundation).
2. 11.2 `CharChooser` refactor with `mode` prop.
3. 11.3 multiselect UX.
4. 11.4 button rename + "Clear from cluster" action.
5. 11.9 chooser preview + zoom (uses the new chooser shape).
6. 11.6 create-new-cluster flow (depends on 11.2 + 11.3 + 11.4).
7. 11.5 cluster overview page.
8. 11.7 home tab switcher.
9. 11.8 theme audit pass (done last so all new surfaces are covered).

Each step ends with: typecheck clean, browser smoke check on at least one
cluster, and a screenshot in both themes for visual changes.

---

## 6. Decisions log

- **2026-05-15 #2** — Switched persistence from JSON sidecars to SQLite (`better-sqlite3`,
  WAL mode) for safety, transactional writes, single-file backup, and cross-edit
  queries. JSON exports become a downstream artifact, not the source of truth.
- **2026-05-15 #2** — Added a keyboard-first **Coptic typing layer** (§3.5): Latin keys
  map to Coptic letters with `Shift`/`Alt`/`Ctrl` modifier overlays for diacritics,
  brackets, and special markers. Active only when a chooser is focused.
- **2026-05-15 #1** — Plan drafted. Next.js App Router + MUI v6 + Tailwind v4; glass theme;
  v1 single-user, no auth.

---

## 7. Open questions (decide as we go)

- Do we want a per-line **translation reference** input, or is it enough to keep a notes field?
- For cluster reassignment, should we offer a **per-page** scope as well, or strictly **corpus-wide**?
- Should newly drawn bboxes auto-suggest a label using the existing skeleton matcher
  (would require a small inference service), or is it manual-only in v1?
- Do we surface the **subcluster** structure in the cluster panel, or treat each cluster as flat for v1?
- Final Latin→Coptic key assignments in §3.5 — user to confirm or tweak.
