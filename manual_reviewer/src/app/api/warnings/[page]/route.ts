import { NextRequest, NextResponse } from "next/server";
import { readInitialBaseline } from "@/lib/pipelineReaders";
import { readBlobEdits } from "@/lib/repo";
import { scorePageTokens } from "@/lib/bigramScorer";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/warnings/[page]
 *
 * Returns per-token warnings for a page based on the bigram model.
 * Lightweight — reads baseline + edits, scores, returns only flagged tokens.
 */
export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ page: string }> },
) {
  const { page } = await ctx.params;
  const pageStr = page.padStart(3, "0");
  const pageInt = parseInt(pageStr, 10);
  if (!Number.isFinite(pageInt)) {
    return NextResponse.json({ error: "invalid page" }, { status: 400 });
  }

  const baseline = await readInitialBaseline(pageStr);
  if (!baseline) {
    return NextResponse.json({ error: "page not found" }, { status: 404 });
  }

  // Apply edits to get effective labels
  const edits = readBlobEdits(pageInt);

  const lines = baseline.lines.map((line) => ({
    line_index: line.line_index,
    tokens: line.tokens.map((tok) => {
      const key = `${line.line_index}:${tok.blob_id}`;
      const ed = edits.get(key);
      const effectiveLabel = ed?.label ?? tok.label ?? null;
      const deleted = ed?.deleted === 1;
      return {
        blob_id: typeof tok.blob_id === "number" ? tok.blob_id : parseInt(tok.blob_id as string, 10),
        line_index: line.line_index,
        label: tok.label ?? null,
        effective_label: effectiveLabel,
        deleted,
        geometry: tok.geometry ?? null,
      };
    }),
  }));

  const warnings = scorePageTokens(lines);

  // --- Orphaned overline detection ---
  // For each line, find baseline overline marks where ALL referencing tokens
  // are deleted, then check if new_bboxes in that x-range have picked up an overline.
  const db = getDb();
  const newBboxRows = db
    .prepare<[number], { id: string; line_index: number; x0: number; x1: number; overline_mark_id: number | null }>(
      "SELECT id, line_index, x0, x1, overline_mark_id FROM new_bboxes WHERE page = ?",
    )
    .all(pageInt);

  for (const line of baseline.lines) {
    // Collect overline marks and their referencing tokens
    const markTokens = new Map<number, { deleted: boolean; x0: number; x1: number }[]>();
    for (const tok of line.tokens) {
      if (tok.overline_mark_id == null) continue;
      const key = `${line.line_index}:${tok.blob_id}`;
      const ed = edits.get(key);
      const deleted = ed?.deleted === 1;
      // Use aabb for image-space x coords
      const aabb = tok.geometry?.aabb;
      if (!aabb) continue;
      if (!markTokens.has(tok.overline_mark_id)) markTokens.set(tok.overline_mark_id, []);
      markTokens.get(tok.overline_mark_id)!.push({ deleted, x0: aabb[0], x1: aabb[2] });
    }

    // Also check blob_edits that SET overline_mark_id on surviving tokens
    const editsWithOverline = new Set<number>();
    for (const tok of line.tokens) {
      const key = `${line.line_index}:${tok.blob_id}`;
      const ed = edits.get(key);
      if (ed?.overline_mark_id != null && ed.deleted !== 1) {
        editsWithOverline.add(ed.overline_mark_id);
      }
    }

    // Find orphaned marks: all referencing tokens are deleted
    for (const [markId, tokens] of markTokens) {
      const allDeleted = tokens.every((t) => t.deleted);
      if (!allDeleted) continue;
      // Already accounted for via blob_edit overline assignment?
      if (editsWithOverline.has(markId)) continue;

      // Get the x-range of this overline group
      const xMin = Math.min(...tokens.map((t) => t.x0));
      const xMax = Math.max(...tokens.map((t) => t.x1));

      // Check if any new_bbox on this line overlapping this x-range has an overline
      const lineNbs = newBboxRows.filter((nb) => nb.line_index === line.line_index);
      const covered = lineNbs.some((nb) => {
        if (nb.overline_mark_id == null) return false;
        const nbXMin = Math.min(nb.x0, nb.x1);
        const nbXMax = Math.max(nb.x0, nb.x1);
        // Overlaps if ranges intersect
        return nbXMax > xMin && nbXMin < xMax;
      });
      if (covered) continue;

      // Orphaned! Warn new_bboxes in this x-range that don't have overline
      const targetNbs = lineNbs.filter((nb) => {
        if (nb.overline_mark_id != null) return false;
        const nbXCenter = (nb.x0 + nb.x1) / 2;
        return nbXCenter >= xMin && nbXCenter <= xMax;
      });

      if (targetNbs.length > 0) {
        for (const nb of targetNbs) {
          warnings.push({
            lineIndex: line.line_index,
            blobId: `nb:${nb.id}`,
            level: "alert",
            reasons: [`overline mark ${markId} orphaned — reassign overline`],
          });
        }
      } else {
        // No new_bboxes in range — emit a line-level warning on the first new_bbox
        const firstNb = lineNbs[0];
        if (firstNb) {
          warnings.push({
            lineIndex: line.line_index,
            blobId: `nb:${firstNb.id}`,
            level: "alert",
            reasons: [`overline mark ${markId} orphaned — no new chars in range`],
          });
        }
      }
    }
  }

  return NextResponse.json({
    page: pageInt,
    warnings,
    stats: {
      total_tokens: lines.reduce((s, l) => s + l.tokens.filter((t) => !t.deleted).length, 0),
      warnings_count: warnings.length,
      alerts_count: warnings.filter((w) => w.level === "alert").length,
    },
  });
}
