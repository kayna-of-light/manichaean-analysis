import "server-only";
import { getDb } from "./db";
import type { Token } from "./zodSchemas";

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

export type LineStatus = "pending" | "in_progress" | "done" | "flagged" | "special";
export type NewBboxKind = "base" | "lacuna_dot" | "mark";

export interface BlobEditRow {
  page: number;
  line_index: number;
  blob_id: string;
  label: string | null;
  diacritics: string | null;
  lacuna_bracket: string | null;
  deleted: number;
  overline_mark_id: number | null;
  source: string;
  updated_at: string;
}

export interface NewBboxRow {
  id: string;
  page: number;
  line_index: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  coord_space: "warped" | "image";
  kind: NewBboxKind;
  label: string | null;
  diacritics: string | null;
  lacuna_bracket: string | null;
  overline_mark_id: number | null;
  missplit_review_id: number | null;
  lost_overline: number;
  created_at: string;
  updated_at: string;
}

export interface ClusterOverrideRow {
  cluster_id: number;
  label: string | null;
  diacritics: string | null;
  note: string | null;
  applied_at: string;
}

export interface TaskRow {
  id: number;
  page: number;
  line_index: number;
  kind: string;
  note: string | null;
  resolved: number;
  created_at: string;
  resolved_at: string | null;
}

export interface LineDuplicateRow {
  id: number;
  page: number;
  source_line_index: number;
  line_index: number;
  ordinal: number;
  created_at: string;
}

export interface EditorialSentenceRow {
  id: number;
  text: string;
  active: number;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface EditorialClusterArrayRow {
  id: number;
  sentence_id: number;
  name: string | null;
  clusters: string;
  active: number;
  min_length: number | null;
  max_length: number | null;
  created_at: string;
  updated_at: string;
}

export interface EditorialArrayWithSentence extends EditorialClusterArrayRow {
  sentence_text: string;
  sentence_active: number;
}

export interface EditorialTokenOverlay {
  label: string;
  sentence_id: number;
  array_id: number;
  sentence_text: string;
  span_position: number;
  span_count: number;
  cluster_array: number[];
}

/* ----------------------------------------------------------------------------
 * Reads
 * ------------------------------------------------------------------------- */

export function readBlobEdits(page: number): Map<string, BlobEditRow> {
  const db = getDb();
  const rows = db
    .prepare<[number], BlobEditRow>(
      "SELECT * FROM blob_edits WHERE page = ?",
    )
    .all(page);
  const m = new Map<string, BlobEditRow>();
  for (const r of rows) m.set(`${r.line_index}:${r.blob_id}`, r);
  return m;
}

export function readNewBboxes(page: number): NewBboxRow[] {
  const db = getDb();
  return db
    .prepare<[number], NewBboxRow>(
      "SELECT * FROM new_bboxes WHERE page = ? ORDER BY line_index, id",
    )
    .all(page);
}

export function readLineStatuses(
  page: number,
): Map<number, { status: LineStatus; note: string | null }> {
  const db = getDb();
  const rows = db
    .prepare<[number], { line_index: number; status: LineStatus; note: string | null }>(
      "SELECT line_index, status, note FROM lines WHERE page = ?",
    )
    .all(page);
  const m = new Map<number, { status: LineStatus; note: string | null }>();
  for (const r of rows) m.set(r.line_index, { status: r.status, note: r.note });
  return m;
}

export function readLineDuplicates(page: number): LineDuplicateRow[] {
  const db = getDb();
  return db
    .prepare<[number], LineDuplicateRow>(
      `SELECT * FROM line_duplicates
       WHERE page = ?
       ORDER BY source_line_index, ordinal, line_index`,
    )
    .all(page);
}

export function readLineDuplicateByLine(page: number, lineIndex: number): LineDuplicateRow | null {
  const db = getDb();
  return db
    .prepare<[number, number], LineDuplicateRow>(
      `SELECT * FROM line_duplicates
       WHERE page = ? AND line_index = ?`,
    )
    .get(page, lineIndex) ?? null;
}

export function readClusterOverride(
  clusterId: number,
): ClusterOverrideRow | null {
  const db = getDb();
  return (
    db
      .prepare<[number], ClusterOverrideRow>(
        "SELECT * FROM cluster_overrides WHERE cluster_id = ?",
      )
      .get(clusterId) ?? null
  );
}

export function readClusterOverridesByIds(
  clusterIds: number[],
): Map<number, ClusterOverrideRow> {
  const m = new Map<number, ClusterOverrideRow>();
  if (clusterIds.length === 0) return m;
  const db = getDb();
  const placeholders = clusterIds.map(() => "?").join(",");
  const rows = db
    .prepare<number[], ClusterOverrideRow>(
      `SELECT * FROM cluster_overrides WHERE cluster_id IN (${placeholders})`,
    )
    .all(...clusterIds);
  for (const r of rows) m.set(r.cluster_id, r);
  return m;
}

export function isBlobUnset(
  page: number,
  lineIndex: number,
  blobId: string | number,
): boolean {
  const db = getDb();
  const r = db
    .prepare<[number, number, string]>(
      "SELECT 1 FROM unset_blobs WHERE page = ? AND line_index = ? AND blob_id = ?",
    )
    .get(page, lineIndex, String(blobId));
  return Boolean(r);
}

export function readOpenTasks(page?: number): TaskRow[] {
  const db = getDb();
  if (page === undefined) {
    return db
      .prepare<[], TaskRow>(
        "SELECT * FROM tasks WHERE resolved = 0 ORDER BY created_at DESC",
      )
      .all();
  }
  return db
    .prepare<[number], TaskRow>(
      "SELECT * FROM tasks WHERE page = ? AND resolved = 0 ORDER BY created_at DESC",
    )
    .all(page);
}

export function readEditorialSentences(): EditorialSentenceRow[] {
  const db = getDb();
  return db
    .prepare<[], EditorialSentenceRow>(
      "SELECT * FROM editorial_sentences ORDER BY lower(text), id",
    )
    .all();
}

export function readEditorialClusterArrays(): EditorialClusterArrayRow[] {
  const db = getDb();
  return db
    .prepare<[], EditorialClusterArrayRow>(
      "SELECT * FROM editorial_cluster_arrays ORDER BY sentence_id, id",
    )
    .all();
}

export function readActiveEditorialArraysWithSentences(): EditorialArrayWithSentence[] {
  const db = getDb();
  return db
    .prepare<[], EditorialArrayWithSentence>(
      `SELECT a.*, s.text AS sentence_text, s.active AS sentence_active
       FROM editorial_cluster_arrays a
       JOIN editorial_sentences s ON s.id = a.sentence_id
       WHERE a.active = 1 AND s.active = 1
       ORDER BY s.id, a.id`,
    )
    .all();
}

/* ----------------------------------------------------------------------------
 * Writes (transactional with audit_log)
 * ------------------------------------------------------------------------- */

function withAudit<T>(
  action: string,
  page: number | null,
  lineIndex: number | null,
  targetId: string | null,
  before: unknown,
  after: unknown,
  fn: () => T,
): T {
  const db = getDb();
  const tx = db.transaction(() => {
    const result = fn();
    db.prepare(
      `INSERT INTO audit_log (action, page, line_index, target_id, before, after)
       VALUES (?, ?, ?, ?, ?, ?)`,
    ).run(
      action,
      page,
      lineIndex,
      targetId,
      before === undefined ? null : JSON.stringify(before),
      after === undefined ? null : JSON.stringify(after),
    );
    db.prepare(
      `INSERT INTO pages(page, status, last_edited_at)
       VALUES (?, 'in_progress', datetime('now'))
       ON CONFLICT(page) DO UPDATE SET last_edited_at = excluded.last_edited_at`,
    ).run(page ?? 0);
    return result;
  });
  return tx.immediate();
}

export interface UpsertEditInput {
  page: number;
  line_index: number;
  blob_id: string;
  label?: string | null;
  diacritics?: string[] | null;
  lacuna_bracket?: string | null;
  deleted?: boolean;
  overline_mark_id?: number | null;
  source?: "manual" | "candidate" | "cluster";
}

function normalizeNewBboxKind(kind: NewBboxKind | null | undefined, label?: string | null): NewBboxKind {
  if (kind === "base" || kind === "lacuna_dot" || kind === "mark") return kind;
  if (label === "." || label === "_lacuna_dot") return "lacuna_dot";
  return "base";
}

export function upsertBlobEdit(input: UpsertEditInput) {
  const db = getDb();
  const key = [input.page, input.line_index, input.blob_id] as const;
  const before = db
    .prepare<[number, number, string], BlobEditRow>(
      "SELECT * FROM blob_edits WHERE page = ? AND line_index = ? AND blob_id = ?",
    )
    .get(...key);

  const after: BlobEditRow = {
    page: input.page,
    line_index: input.line_index,
    blob_id: input.blob_id,
    label: input.label !== undefined ? input.label : (before?.label ?? null),
    diacritics: input.diacritics
      ? JSON.stringify(input.diacritics)
      : (before?.diacritics ?? null),
    lacuna_bracket:
      input.lacuna_bracket !== undefined
        ? input.lacuna_bracket
        : (before?.lacuna_bracket ?? null),
    deleted:
      input.deleted === undefined ? (before?.deleted ?? 0) : input.deleted ? 1 : 0,
    overline_mark_id:
      input.overline_mark_id !== undefined
        ? input.overline_mark_id
        : (before?.overline_mark_id ?? null),
    source: input.source ?? "manual",
    updated_at: new Date().toISOString(),
  };

  return withAudit(
    "blob_edit.upsert",
    input.page,
    input.line_index,
    input.blob_id,
    before,
    after,
    () => {
      db.prepare(
        `INSERT INTO blob_edits
         (page, line_index, blob_id, label, diacritics, lacuna_bracket,
          deleted, overline_mark_id, source, updated_at)
         VALUES (@page, @line_index, @blob_id, @label, @diacritics,
                 @lacuna_bracket, @deleted, @overline_mark_id, @source, @updated_at)
         ON CONFLICT(page, line_index, blob_id) DO UPDATE SET
           label = excluded.label,
           diacritics = excluded.diacritics,
           lacuna_bracket = excluded.lacuna_bracket,
           deleted = excluded.deleted,
           overline_mark_id = excluded.overline_mark_id,
           source = excluded.source,
           updated_at = excluded.updated_at`,
      ).run(after);
      return after;
    },
  );
}

export function setLineStatus(
  page: number,
  lineIndex: number,
  status: LineStatus,
  note: string | null = null,
) {
  const db = getDb();
  const before = db
    .prepare<[number, number]>(
      "SELECT status, note FROM lines WHERE page = ? AND line_index = ?",
    )
    .get(page, lineIndex);
  return withAudit(
    "line.set_status",
    page,
    lineIndex,
    null,
    before,
    { status, note },
    () => {
      db.prepare(
        `INSERT INTO lines (page, line_index, status, note, updated_at)
         VALUES (?, ?, ?, ?, datetime('now'))
         ON CONFLICT(page, line_index) DO UPDATE SET
           status = excluded.status,
           note = excluded.note,
           updated_at = excluded.updated_at`,
      ).run(page, lineIndex, status, note);
    },
  );
}

export function createLineDuplicate(input: {
  page: number;
  source_line_index: number;
  line_index: number;
  ordinal: number;
}): LineDuplicateRow {
  const db = getDb();
  const after = {
    ...input,
    created_at: new Date().toISOString(),
  };
  return withAudit(
    "line_duplicate.create",
    input.page,
    input.source_line_index,
    String(input.line_index),
    null,
    after,
    () => {
      db.prepare(
        `INSERT INTO line_duplicates
         (page, source_line_index, line_index, ordinal, created_at)
         VALUES (@page, @source_line_index, @line_index, @ordinal, @created_at)`,
      ).run(after);
      return db
        .prepare<[number, number], LineDuplicateRow>(
          `SELECT * FROM line_duplicates
           WHERE page = ? AND line_index = ?`,
        )
        .get(input.page, input.line_index)!;
    },
  );
}

export function createNewBbox(input: Omit<NewBboxRow, "created_at" | "updated_at" | "id" | "lost_overline" | "kind"> & {
  id?: string;
  lost_overline?: number;
  kind?: NewBboxKind | null;
}) {
  const db = getDb();
  const id = input.id ?? `new_p${String(input.page).padStart(3, "0")}_l${String(
    input.line_index,
  ).padStart(2, "0")}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
  const after = {
    ...input,
    id,
    kind: normalizeNewBboxKind(input.kind, input.label),
    lost_overline: input.lost_overline ?? 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  return withAudit(
    "new_bbox.create",
    input.page,
    input.line_index,
    id,
    null,
    after,
    () => {
      db.prepare(
        `INSERT INTO new_bboxes
         (id, page, line_index, x0, y0, x1, y1, coord_space, kind, label,
          diacritics, lacuna_bracket, overline_mark_id, lost_overline, missplit_review_id, created_at, updated_at)
         VALUES (@id, @page, @line_index, @x0, @y0, @x1, @y1, @coord_space, @kind,
                 @label, @diacritics, @lacuna_bracket, @overline_mark_id, @lost_overline, @missplit_review_id, @created_at, @updated_at)`,
      ).run(after);
      return after;
    },
  );
}

export function deleteNewBbox(id: string) {
  const db = getDb();
  const before = db
    .prepare<[string], NewBboxRow>("SELECT * FROM new_bboxes WHERE id = ?")
    .get(id);
  if (!before) return null;
  return withAudit(
    "new_bbox.delete",
    before.page,
    before.line_index,
    id,
    before,
    null,
    () => {
      db.prepare("DELETE FROM new_bboxes WHERE id = ?").run(id);
      return before;
    },
  );
}

export function updateNewBbox(
  id: string,
  updates: {
    line_index?: number;
    x0?: number;
    y0?: number;
    x1?: number;
    y1?: number;
    coord_space?: "warped" | "image";
    kind?: NewBboxKind | null;
    label?: string | null;
    diacritics?: string | null;
    lacuna_bracket?: string | null;
    overline_mark_id?: number | null;
  },
) {
  const db = getDb();
  const before = db
    .prepare<[string], NewBboxRow>("SELECT * FROM new_bboxes WHERE id = ?")
    .get(id);
  if (!before) return null;
  const after = {
    ...before,
    line_index: updates.line_index !== undefined ? updates.line_index : before.line_index,
    x0: updates.x0 !== undefined ? updates.x0 : before.x0,
    y0: updates.y0 !== undefined ? updates.y0 : before.y0,
    x1: updates.x1 !== undefined ? updates.x1 : before.x1,
    y1: updates.y1 !== undefined ? updates.y1 : before.y1,
    coord_space: updates.coord_space !== undefined ? updates.coord_space : before.coord_space,
    kind: updates.kind !== undefined ? normalizeNewBboxKind(updates.kind, updates.label ?? before.label) : before.kind,
    label: updates.label !== undefined ? updates.label : before.label,
    diacritics: updates.diacritics !== undefined ? updates.diacritics : before.diacritics,
    lacuna_bracket:
      updates.lacuna_bracket !== undefined ? updates.lacuna_bracket : before.lacuna_bracket,
    overline_mark_id:
      updates.overline_mark_id !== undefined ? updates.overline_mark_id : before.overline_mark_id,
    updated_at: new Date().toISOString(),
  };
  return withAudit(
    "new_bbox.update",
    before.page,
    before.line_index,
    id,
    before,
    after,
    () => {
      db.prepare(
        `UPDATE new_bboxes
         SET line_index = @line_index,
             x0 = @x0,
             y0 = @y0,
             x1 = @x1,
             y1 = @y1,
             coord_space = @coord_space,
             kind = @kind,
             label = @label,
             diacritics = @diacritics,
             lacuna_bracket = @lacuna_bracket,
             overline_mark_id = @overline_mark_id,
             updated_at = @updated_at
         WHERE id = @id`,
      ).run({
        id,
        line_index: after.line_index,
        x0: after.x0,
        y0: after.y0,
        x1: after.x1,
        y1: after.y1,
        coord_space: after.coord_space,
        kind: after.kind,
        label: after.label,
        diacritics: after.diacritics,
        lacuna_bracket: after.lacuna_bracket,
        overline_mark_id: after.overline_mark_id,
        updated_at: after.updated_at,
      });
      return after;
    },
  );
}

export function moveNewBboxToLine(id: string, newLineIndex: number) {
  const db = getDb();
  const before = db
    .prepare<[string], NewBboxRow>("SELECT * FROM new_bboxes WHERE id = ?")
    .get(id);
  if (!before) return null;
  const after = { ...before, line_index: newLineIndex, updated_at: new Date().toISOString() };
  return withAudit(
    "new_bbox.move_line",
    before.page,
    before.line_index,
    id,
    before,
    after,
    () => {
      db.prepare(
        "UPDATE new_bboxes SET line_index = @line_index, updated_at = @updated_at WHERE id = @id",
      ).run({ id, line_index: newLineIndex, updated_at: after.updated_at });
      return after;
    },
  );
}

export function applyClusterOverride(
  clusterId: number,
  label: string | null,
  diacritics: string[] | null = null,
  note: string | null = null,
) {
  const db = getDb();
  const before = readClusterOverride(clusterId);
  const after: ClusterOverrideRow = {
    cluster_id: clusterId,
    label,
    diacritics: diacritics ? JSON.stringify(diacritics) : null,
    note,
    applied_at: new Date().toISOString(),
  };
  return withAudit(
    "cluster_override.apply",
    null,
    null,
    String(clusterId),
    before,
    after,
    () => {
      db.prepare(
        `INSERT INTO cluster_overrides
         (cluster_id, label, diacritics, note, applied_at)
         VALUES (@cluster_id, @label, @diacritics, @note, @applied_at)
         ON CONFLICT(cluster_id) DO UPDATE SET
           label = excluded.label,
           diacritics = excluded.diacritics,
           note = excluded.note,
           applied_at = excluded.applied_at`,
      ).run(after);
      return after;
    },
  );
}

export function unsetBlob(
  page: number,
  lineIndex: number,
  blobId: string,
  removedFromCluster: number | null,
) {
  const db = getDb();
  return withAudit(
    "cluster.unset_blob",
    page,
    lineIndex,
    blobId,
    null,
    { removedFromCluster },
    () => {
      db.prepare(
        `INSERT OR REPLACE INTO unset_blobs
         (page, line_index, blob_id, removed_from_cluster, moved_at)
         VALUES (?, ?, ?, ?, datetime('now'))`,
      ).run(page, lineIndex, blobId, removedFromCluster);
      // A blob being unset shouldn't also be tracked as reassigned.
      db.prepare(
        `DELETE FROM cluster_reassignments
         WHERE page = ? AND line_index = ? AND blob_id = ?`,
      ).run(page, lineIndex, blobId);
    },
  );
}

export interface ClusterReassignmentRow {
  page: number;
  line_index: number;
  blob_id: string;
  from_cluster: number | null;
  to_cluster: number;
  note: string | null;
  moved_at: string;
}

/** Move a single blob from `fromCluster` (informational) to `toCluster`. */
export function reassignBlob(
  page: number,
  lineIndex: number,
  blobId: string,
  fromCluster: number | null,
  toCluster: number,
  note: string | null = null,
) {
  const db = getDb();
  return withAudit(
    "cluster.reassign_blob",
    page,
    lineIndex,
    blobId,
    { fromCluster },
    { toCluster, note },
    () => {
      db.prepare(
        `INSERT INTO cluster_reassignments
         (page, line_index, blob_id, from_cluster, to_cluster, note, moved_at)
         VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
         ON CONFLICT(page, line_index, blob_id) DO UPDATE SET
           from_cluster = excluded.from_cluster,
           to_cluster   = excluded.to_cluster,
           note         = excluded.note,
           moved_at     = excluded.moved_at`,
      ).run(page, lineIndex, blobId, fromCluster, toCluster, note);
      // Reassigning a previously-unset blob brings it back into a cluster.
      db.prepare(
        `DELETE FROM unset_blobs
         WHERE page = ? AND line_index = ? AND blob_id = ?`,
      ).run(page, lineIndex, blobId);
    },
  );
}

/** Clear an existing reassignment, returning the blob to its original cluster. */
export function clearReassignment(
  page: number,
  lineIndex: number,
  blobId: string,
) {
  const db = getDb();
  const before = db
    .prepare<[number, number, string], ClusterReassignmentRow>(
      `SELECT * FROM cluster_reassignments
       WHERE page = ? AND line_index = ? AND blob_id = ?`,
    )
    .get(page, lineIndex, blobId) ?? null;
  if (!before) return null;
  return withAudit(
    "cluster.clear_reassignment",
    page,
    lineIndex,
    blobId,
    before,
    null,
    () => {
      db.prepare(
        `DELETE FROM cluster_reassignments
         WHERE page = ? AND line_index = ? AND blob_id = ?`,
      ).run(page, lineIndex, blobId);
    },
  );
}

/** All reassignments for a single page. Keyed by `lineIndex:blobId`. */
export function readReassignmentsForPage(
  page: number,
): Map<string, ClusterReassignmentRow> {
  const db = getDb();
  const rows = db
    .prepare<[number], ClusterReassignmentRow>(
      `SELECT * FROM cluster_reassignments WHERE page = ?`,
    )
    .all(page);
  const m = new Map<string, ClusterReassignmentRow>();
  for (const r of rows) m.set(`${r.line_index}:${r.blob_id}`, r);
  return m;
}

/** All blobs reassigned INTO a given cluster (from anywhere in the corpus). */
export function readReassignmentsToCluster(
  toCluster: number,
): ClusterReassignmentRow[] {
  const db = getDb();
  return db
    .prepare<[number], ClusterReassignmentRow>(
      `SELECT * FROM cluster_reassignments WHERE to_cluster = ?`,
    )
    .all(toCluster);
}

/** All blobs reassigned AWAY from a given cluster. Keyed by `page:line:blob`. */
export function readReassignmentsFromCluster(
  fromCluster: number,
): Map<string, ClusterReassignmentRow> {
  const db = getDb();
  const rows = db
    .prepare<[number], ClusterReassignmentRow>(
      `SELECT * FROM cluster_reassignments WHERE from_cluster = ?`,
    )
    .all(fromCluster);
  const m = new Map<string, ClusterReassignmentRow>();
  for (const r of rows) {
    m.set(`${String(r.page).padStart(3, "0")}:${r.line_index}:${r.blob_id}`, r);
  }
  return m;
}

export function resetLine(page: number, lineIndex: number) {
  const db = getDb();
  const beforeEdits = db
    .prepare<[number, number], BlobEditRow>(
      "SELECT * FROM blob_edits WHERE page = ? AND line_index = ?",
    )
    .all(page, lineIndex);
  const beforeUnset = db
    .prepare<[number, number]>(
      "SELECT * FROM unset_blobs WHERE page = ? AND line_index = ?",
    )
    .all(page, lineIndex);
  const beforeNewBboxes = db
    .prepare<[number, number], NewBboxRow>(
      "SELECT * FROM new_bboxes WHERE page = ? AND line_index = ?",
    )
    .all(page, lineIndex);
  const beforeDuplicate = db
    .prepare<[number, number], LineDuplicateRow>(
      "SELECT * FROM line_duplicates WHERE page = ? AND line_index = ?",
    )
    .all(page, lineIndex);
  const beforeStatus = beforeDuplicate.length
    ? db
        .prepare<[number, number]>(
          "SELECT * FROM lines WHERE page = ? AND line_index = ?",
        )
        .all(page, lineIndex)
    : [];

  return withAudit(
    "line.reset",
    page,
    lineIndex,
    null,
    {
      edits: beforeEdits,
      unset: beforeUnset,
      new_bboxes: beforeNewBboxes,
      duplicate: beforeDuplicate,
      status: beforeStatus,
    },
    null,
    () => {
      db.prepare("DELETE FROM blob_edits WHERE page = ? AND line_index = ?").run(
        page,
        lineIndex,
      );
      db.prepare("DELETE FROM unset_blobs WHERE page = ? AND line_index = ?").run(
        page,
        lineIndex,
      );
      db.prepare("DELETE FROM new_bboxes WHERE page = ? AND line_index = ?").run(
        page,
        lineIndex,
      );
      if (beforeDuplicate.length) {
        db.prepare("DELETE FROM line_duplicates WHERE page = ? AND line_index = ?").run(
          page,
          lineIndex,
        );
        db.prepare("DELETE FROM lines WHERE page = ? AND line_index = ?").run(
          page,
          lineIndex,
        );
      }
      return {
        deleted_edits: beforeEdits.length,
        deleted_unset: beforeUnset.length,
        deleted_new_bboxes: beforeNewBboxes.length,
        deleted_duplicate_lines: beforeDuplicate.length,
      };
    },
  );
}

export function createTask(
  page: number,
  lineIndex: number,
  kind: string,
  note: string | null = null,
) {
  const db = getDb();
  return withAudit("task.create", page, lineIndex, null, null, { kind, note }, () => {
    const info = db
      .prepare(
        `INSERT INTO tasks (page, line_index, kind, note) VALUES (?, ?, ?, ?)`,
      )
      .run(page, lineIndex, kind, note);
    return Number(info.lastInsertRowid);
  });
}

export function createEditorialSentence(
  text: string,
  active = true,
  note: string | null = null,
): EditorialSentenceRow {
  const db = getDb();
  const after = {
    text,
    active: active ? 1 : 0,
    note,
    updated_at: new Date().toISOString(),
  };
  return withAudit("editorial_sentence.create", null, null, text, null, after, () => {
    db.prepare(
      `INSERT INTO editorial_sentences (text, active, note, created_at, updated_at)
       VALUES (@text, @active, @note, datetime('now'), @updated_at)
       ON CONFLICT(text) DO UPDATE SET
         active = excluded.active,
         note = excluded.note,
         updated_at = excluded.updated_at`,
    ).run(after);
    return db
      .prepare<[string], EditorialSentenceRow>(
        "SELECT * FROM editorial_sentences WHERE text = ?",
      )
      .get(text)!;
  });
}

export function updateEditorialSentence(
  id: number,
  updates: { text?: string; active?: boolean; note?: string | null },
): EditorialSentenceRow | null {
  const db = getDb();
  const before = db
    .prepare<[number], EditorialSentenceRow>(
      "SELECT * FROM editorial_sentences WHERE id = ?",
    )
    .get(id);
  if (!before) return null;
  const after: EditorialSentenceRow = {
    ...before,
    text: updates.text !== undefined ? updates.text : before.text,
    active: updates.active !== undefined ? (updates.active ? 1 : 0) : before.active,
    note: updates.note !== undefined ? updates.note : before.note,
    updated_at: new Date().toISOString(),
  };
  return withAudit("editorial_sentence.update", null, null, String(id), before, after, () => {
    db.prepare(
      `UPDATE editorial_sentences
       SET text = @text, active = @active, note = @note, updated_at = @updated_at
       WHERE id = @id`,
    ).run(after);
    return after;
  });
}

export function deleteEditorialSentence(id: number): EditorialSentenceRow | null {
  const db = getDb();
  const before = db
    .prepare<[number], EditorialSentenceRow>(
      "SELECT * FROM editorial_sentences WHERE id = ?",
    )
    .get(id);
  if (!before) return null;
  return withAudit("editorial_sentence.delete", null, null, String(id), before, null, () => {
    db.prepare("DELETE FROM editorial_sentences WHERE id = ?").run(id);
    return before;
  });
}

export function createEditorialClusterArray(
  sentenceId: number,
  clusters: number[],
  name: string | null = null,
  active = true,
  minLength: number | null = null,
  maxLength: number | null = null,
): EditorialClusterArrayRow {
  const db = getDb();
  const after = {
    sentence_id: sentenceId,
    name,
    clusters: JSON.stringify(clusters),
    active: active ? 1 : 0,
    min_length: minLength,
    max_length: maxLength,
    updated_at: new Date().toISOString(),
  };
  return withAudit("editorial_array.create", null, null, String(sentenceId), null, after, () => {
    const info = db.prepare(
      `INSERT INTO editorial_cluster_arrays
       (sentence_id, name, clusters, active, min_length, max_length, created_at, updated_at)
       VALUES (@sentence_id, @name, @clusters, @active, @min_length, @max_length, datetime('now'), @updated_at)`,
    ).run(after);
    return db
      .prepare<[number], EditorialClusterArrayRow>(
        "SELECT * FROM editorial_cluster_arrays WHERE id = ?",
      )
      .get(Number(info.lastInsertRowid))!;
  });
}

export function updateEditorialClusterArray(
  id: number,
  updates: { clusters?: number[]; name?: string | null; active?: boolean; min_length?: number | null; max_length?: number | null },
): EditorialClusterArrayRow | null {
  const db = getDb();
  const before = db
    .prepare<[number], EditorialClusterArrayRow>(
      "SELECT * FROM editorial_cluster_arrays WHERE id = ?",
    )
    .get(id);
  if (!before) return null;
  const after: EditorialClusterArrayRow = {
    ...before,
    name: updates.name !== undefined ? updates.name : before.name,
    clusters: updates.clusters !== undefined ? JSON.stringify(updates.clusters) : before.clusters,
    active: updates.active !== undefined ? (updates.active ? 1 : 0) : before.active,
    min_length: updates.min_length !== undefined ? updates.min_length : before.min_length,
    max_length: updates.max_length !== undefined ? updates.max_length : before.max_length,
    updated_at: new Date().toISOString(),
  };
  return withAudit("editorial_array.update", null, null, String(id), before, after, () => {
    db.prepare(
      `UPDATE editorial_cluster_arrays
       SET name = @name, clusters = @clusters, active = @active, min_length = @min_length, max_length = @max_length, updated_at = @updated_at
       WHERE id = @id`,
    ).run(after);
    return after;
  });
}

export function deleteEditorialClusterArray(id: number): EditorialClusterArrayRow | null {
  const db = getDb();
  const before = db
    .prepare<[number], EditorialClusterArrayRow>(
      "SELECT * FROM editorial_cluster_arrays WHERE id = ?",
    )
    .get(id);
  if (!before) return null;
  return withAudit("editorial_array.delete", null, null, String(id), before, null, () => {
    db.prepare("DELETE FROM editorial_cluster_arrays WHERE id = ?").run(id);
    return before;
  });
}

export function resolveTask(taskId: number) {
  const db = getDb();
  const before = db
    .prepare<[number], TaskRow>("SELECT * FROM tasks WHERE id = ?")
    .get(taskId);
  if (!before) return null;
  return withAudit("task.resolve", before.page, before.line_index, String(taskId), before, null, () => {
    db.prepare(
      "UPDATE tasks SET resolved = 1, resolved_at = datetime('now') WHERE id = ?",
    ).run(taskId);
  });
}

/* ----------------------------------------------------------------------------
 * Effective token: merge pipeline token with manual edits + cluster overrides
 * ------------------------------------------------------------------------- */

export interface EffectiveToken extends Token {
  effective_label: string | null;
  user_modified: boolean;
  unset: boolean;
  deleted: boolean;
  user_edit?: BlobEditRow;
  cluster_override?: ClusterOverrideRow;
  editorial_overlay?: EditorialTokenOverlay;
}

export function mergeTokens(
  page: number,
  tokens: Token[],
  edits: Map<string, BlobEditRow>,
  clusterOverrides: Map<number, ClusterOverrideRow>,
  unsetSet: Set<string>,
  reassignments?: Map<string, ClusterReassignmentRow>,
  editorialOverlays?: Map<string, EditorialTokenOverlay>,
): EffectiveToken[] {
  return tokens.map((t) => {
    const key = `${t.line_index}:${t.edit_id ?? t.blob_id}`;
    // Fallback: if edit_id is suffixed (e.g. "2#1") but DB has raw blob_id ("2"),
    // try the raw key. This handles edits created by the missplit resolve endpoint.
    const rawKey = t.edit_id && t.edit_id !== String(t.blob_id)
      ? `${t.line_index}:${t.blob_id}`
      : null;
    const edit = edits.get(key) ?? (rawKey ? edits.get(rawKey) : undefined) ?? undefined;
    const reassign = reassignments?.get(key) ?? null;
    const originalClusterInt = parseInt(t.cluster, 10);
    const effectiveClusterInt = reassign ? reassign.to_cluster
      : Number.isFinite(originalClusterInt) ? originalClusterInt
      : null;
    const co = effectiveClusterInt != null
      ? clusterOverrides.get(effectiveClusterInt)
      : undefined;
    const eo = editorialOverlays?.get(key);
    const deleted = Boolean(edit?.deleted);
    const manuallyCleared = Boolean(edit && !deleted && edit.label === "");
    const unset = unsetSet.has(key) || manuallyCleared;
    // Precedence: deleted > user edit > editorial overlay > cluster override > geometric > manual_override > pipeline label
    const effective = deleted
      ? null
      : (edit?.label ??
        eo?.label ??
        (co && !unset ? co.label : null) ??
        t.geometric_override?.label ??
        t.manual_override?.label ??
        t.label ??
        null);
    const userModified = Boolean(edit) || Boolean(eo) || Boolean(co) || Boolean(reassign);
    // Overline: if user has a blob_edit row, its overline_mark_id wins (even if null = cleared)
    const overlineMarkId = edit
      ? (edit.overline_mark_id ?? null)
      : (t.overline_mark_id ?? null);
    void page;
    return {
      ...t,
      cluster: effectiveClusterInt != null
        ? String(effectiveClusterInt).padStart(3, "0")
        : t.cluster,
      overline_mark_id: overlineMarkId,
      effective_label: effective,
      user_modified: userModified,
      unset,
      deleted,
      user_edit: edit,
      cluster_override: co,
      editorial_overlay: eo,
    };
  });
}

/* --------------------------------------------------------------------------
 * Missplit Reviews
 * -------------------------------------------------------------------------- */

export interface MissplitReviewRow {
  id: number;
  page: number;
  line_index: number;
  blob_ids: string;
  status: string;
  new_labels: string | null;
  created_at: string;
  resolved_at: string | null;
}

export function readMissplitReviews(): MissplitReviewRow[] {
  const db = getDb();
  return db
    .prepare("SELECT * FROM missplit_reviews ORDER BY page, line_index")
    .all() as MissplitReviewRow[];
}

export function readMissplitReviewsByKey(
  page: number,
  lineIndex: number,
  blobIds: number[],
): MissplitReviewRow | undefined {
  const db = getDb();
  const key = JSON.stringify(blobIds);
  return db
    .prepare(
      "SELECT * FROM missplit_reviews WHERE page = ? AND line_index = ? AND blob_ids = ?",
    )
    .get(page, lineIndex, key) as MissplitReviewRow | undefined;
}

export function resolveMissplitAsCorrect(
  page: number,
  lineIndex: number,
  blobIds: number[],
): number {
  const db = getDb();
  const key = JSON.stringify(blobIds);
  const existing = db
    .prepare(
      "SELECT id FROM missplit_reviews WHERE page = ? AND line_index = ? AND blob_ids = ?",
    )
    .get(page, lineIndex, key) as { id: number } | undefined;

  if (existing) {
    db.prepare(
      `UPDATE missplit_reviews
       SET status = 'correct', resolved_at = datetime('now')
       WHERE id = ?`,
    ).run(existing.id);
    return existing.id;
  }

  const result = db.prepare(
    `INSERT INTO missplit_reviews (page, line_index, blob_ids, status, resolved_at)
     VALUES (?, ?, ?, 'correct', datetime('now'))`,
  ).run(page, lineIndex, key);
  return Number(result.lastInsertRowid);
}

export function resolveMissplitAsFixed(
  page: number,
  lineIndex: number,
  blobIds: number[],
  newLabels: string[],
): number {
  const db = getDb();
  const key = JSON.stringify(blobIds);
  const labelsJson = JSON.stringify(newLabels);
  const existing = db
    .prepare(
      "SELECT id FROM missplit_reviews WHERE page = ? AND line_index = ? AND blob_ids = ?",
    )
    .get(page, lineIndex, key) as { id: number } | undefined;

  if (existing) {
    db.prepare(
      `UPDATE missplit_reviews
       SET status = 'fixed', new_labels = ?, resolved_at = datetime('now')
       WHERE id = ?`,
    ).run(labelsJson, existing.id);
    return existing.id;
  }

  const result = db.prepare(
    `INSERT INTO missplit_reviews (page, line_index, blob_ids, status, new_labels, resolved_at)
     VALUES (?, ?, ?, 'fixed', ?, datetime('now'))`,
  ).run(page, lineIndex, key, labelsJson);
  return Number(result.lastInsertRowid);
}

/**
 * Revert a missplit review: delete the review record, remove any new_bboxes
 * linked to that review, and un-delete the original blobs.
 */
export function revertMissplitReview(reviewId: number) {
  const db = getDb();
  const review = db
    .prepare<[number], { id: number; page: number; line_index: number; blob_ids: string; status: string }>(
      "SELECT id, page, line_index, blob_ids, status FROM missplit_reviews WHERE id = ?",
    )
    .get(reviewId);
  if (!review) return null;

  const blobIds: number[] = JSON.parse(review.blob_ids);

  const doRevert = db.transaction(() => {
    // 1. Un-delete original blobs
    for (const blobId of blobIds) {
      const existing = db
        .prepare("SELECT deleted FROM blob_edits WHERE page = ? AND line_index = ? AND blob_id = ?")
        .get(review.page, review.line_index, String(blobId)) as { deleted: number } | undefined;
      if (existing?.deleted) {
        db.prepare(
          `UPDATE blob_edits SET deleted = 0, updated_at = datetime('now')
           WHERE page = ? AND line_index = ? AND blob_id = ?`,
        ).run(review.page, review.line_index, String(blobId));
      }
    }

    // 2. Delete new_bboxes linked to this specific review
    const bboxes = db
      .prepare<[number], { id: string }>(
        "SELECT id FROM new_bboxes WHERE missplit_review_id = ?",
      )
      .all(reviewId);

    if (bboxes.length > 0) {
      // Linked via FK — only delete those belonging to this review
      for (const bbox of bboxes) {
        deleteNewBbox(bbox.id);
      }
    } else {
      // Legacy: no FK linkage — fall back to spatial overlap with original blob aabbs
      // Get the original blob aabb from blob_edits or detection
      // For safety, only delete bboxes that spatially match the original blobs
      const origAabbs = blobIds.map((bid) => {
        // We don't have the original aabb stored, so fall back to page+line
        return null;
      });
      // If we can't spatially match, delete ALL on the line (legacy behavior)
      const lineBboxes = db
        .prepare<[number, number], { id: string }>(
          "SELECT id FROM new_bboxes WHERE page = ? AND line_index = ?",
        )
        .all(review.page, review.line_index);
      for (const bbox of lineBboxes) {
        deleteNewBbox(bbox.id);
      }
    }

    // 3. Delete the review record
    db.prepare("DELETE FROM missplit_reviews WHERE id = ?").run(reviewId);
  });

  doRevert();
  return { page: review.page, lineIndex: review.line_index };
}
