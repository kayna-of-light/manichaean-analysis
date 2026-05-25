import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { EXPORT_DIR } from "@/lib/paths";
import { getDb } from "@/lib/db";
import {
  buildCanonicalLineLayout,
  canonicalizeLineIndex,
  type CanonicalLineLayout,
} from "@/lib/canonicalLines";
import { readV2Geometry } from "@/lib/pipelineReaders";

export const dynamic = "force-dynamic";

/**
 * Read-only export of all manual edits as a single JSON document, written
 * to data/exports/reviewer-export-<timestamp>.json and returned in the
 * response body.
 */
export async function POST() {
  const db = getDb();
  fs.mkdirSync(EXPORT_DIR, { recursive: true });

  const rawBlobEdits = db.prepare("SELECT * FROM blob_edits").all() as LineIndexedRow[];
  const rawNewBboxes = db.prepare("SELECT * FROM new_bboxes").all() as LineIndexedRow[];
  const cluster_overrides = db.prepare("SELECT * FROM cluster_overrides").all();
  const rawUnsetBlobs = db.prepare("SELECT * FROM unset_blobs").all() as LineIndexedRow[];
  const rawLines = db.prepare("SELECT * FROM lines").all() as LineIndexedRow[];
  const tasks = db.prepare("SELECT * FROM tasks").all();

  const layouts = await loadLayouts([
    ...rawBlobEdits,
    ...rawNewBboxes,
    ...rawUnsetBlobs,
    ...rawLines,
  ]);
  const blob_edits = dedupeLineRows(
    canonicalizeRows(rawBlobEdits, layouts),
    (row) => `${row.page}:${row.line_index}:${row.blob_id}`,
  );
  const new_bboxes = canonicalizeRows(rawNewBboxes, layouts);
  const unset_blobs = dedupeLineRows(
    canonicalizeRows(rawUnsetBlobs, layouts),
    (row) => `${row.page}:${row.line_index}:${row.blob_id}`,
  );
  const lines = dedupeLineRows(
    canonicalizeRows(rawLines, layouts),
    (row) => `${row.page}:${row.line_index}`,
  );

  const payload = {
    exported_at: new Date().toISOString(),
    blob_edits,
    new_bboxes,
    cluster_overrides,
    unset_blobs,
    lines,
    tasks,
  };
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const target = path.join(EXPORT_DIR, `reviewer-export-${stamp}.json`);
  fs.writeFileSync(target, JSON.stringify(payload, null, 2), "utf8");
  return NextResponse.json({ ok: true, target, summary: {
    blob_edits: blob_edits.length,
    new_bboxes: new_bboxes.length,
    cluster_overrides: cluster_overrides.length,
    unset_blobs: unset_blobs.length,
    lines: lines.length,
    tasks: tasks.length,
  } });
}

interface LineIndexedRow {
  page: number;
  line_index: number;
  updated_at?: string;
  blob_id?: string;
  [key: string]: unknown;
}

async function loadLayouts(rows: LineIndexedRow[]): Promise<Map<number, CanonicalLineLayout | null>> {
  const layouts = new Map<number, CanonicalLineLayout | null>();
  const pages = [...new Set(rows.map((row) => row.page))];
  await Promise.all(
    pages.map(async (page) => {
      const pageId = String(page).padStart(3, "0");
      layouts.set(page, buildCanonicalLineLayout(await readV2Geometry(pageId)));
    }),
  );
  return layouts;
}

function canonicalizeRows<T extends LineIndexedRow>(
  rows: T[],
  layouts: Map<number, CanonicalLineLayout | null>,
): T[] {
  return rows.map((row) => ({
    ...row,
    line_index: canonicalizeLineIndex(layouts.get(row.page), row.line_index),
  }));
}

function dedupeLineRows<T extends LineIndexedRow>(rows: T[], keyForRow: (row: T) => string): T[] {
  const byKey = new Map<string, T>();
  for (const row of rows) {
    const key = keyForRow(row);
    const existing = byKey.get(key);
    if (!existing || String(row.updated_at ?? "") >= String(existing.updated_at ?? "")) {
      byKey.set(key, row);
    }
  }
  return [...byKey.values()];
}
