import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { EXPORT_DIR } from "@/lib/paths";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * Read-only export of all manual edits as a single JSON document, written
 * to data/exports/reviewer-export-<timestamp>.json and returned in the
 * response body.
 */
export async function POST() {
  const db = getDb();
  fs.mkdirSync(EXPORT_DIR, { recursive: true });

  const blob_edits = db.prepare("SELECT * FROM blob_edits").all();
  const new_bboxes = db.prepare("SELECT * FROM new_bboxes").all();
  const cluster_overrides = db.prepare("SELECT * FROM cluster_overrides").all();
  const unset_blobs = db.prepare("SELECT * FROM unset_blobs").all();
  const lines = db.prepare("SELECT * FROM lines").all();
  const tasks = db.prepare("SELECT * FROM tasks").all();

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
