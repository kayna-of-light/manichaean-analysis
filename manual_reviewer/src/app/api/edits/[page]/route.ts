import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import {
  createNewBbox,
  deleteNewBbox,
  resetLine,
  setLineStatus,
  updateNewBbox,
  upsertBlobEdit,
  readBlobEdits,
  readNewBboxes,
} from "@/lib/repo";
import { EditBlobSchema, NewBboxInputSchema } from "@/lib/zodSchemas";
import { applyEditToModel, invalidateModel, reinforceConfirmedLine } from "@/lib/bigramScorer";
import { buildCanonicalLineLayout, canonicalizeLineIndex } from "@/lib/canonicalLines";
import { readInitialBaseline, readV2Geometry } from "@/lib/pipelineReaders";

export const dynamic = "force-dynamic";

const UpdateNewBboxSchema = z.object({
  id: z.string(),
  label: z.string().nullable().optional(),
  diacritics: z.array(z.string()).optional(),
  overline_mark_id: z.number().nullable().optional(),
});

const BodySchema = z.object({
  blob_edits: z.array(EditBlobSchema).optional(),
  new_bboxes: z.array(NewBboxInputSchema).optional(),
  update_new_bboxes: z.array(UpdateNewBboxSchema).optional(),
  delete_new_bboxes: z.array(z.string()).optional(),
  line_status: z
    .object({
      line_index: z.number(),
      status: z.enum(["pending", "in_progress", "done", "flagged", "special"]),
      note: z.string().nullable().optional(),
    })
    .optional(),
  reset_line: z.object({ line_index: z.number() }).optional(),
});

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ page: string }> },
) {
  const { page } = await ctx.params;
  const pageInt = parseInt(page, 10);
  if (!Number.isFinite(pageInt)) {
    return NextResponse.json({ error: "invalid page" }, { status: 400 });
  }
  let body: z.infer<typeof BodySchema>;
  try {
    body = BodySchema.parse(await req.json());
  } catch (err) {
    return NextResponse.json(
      { error: "bad request", detail: (err as Error).message },
      { status: 400 },
    );
  }

  const pageStr = String(pageInt).padStart(3, "0");
  const canonicalLayout = buildCanonicalLineLayout(await readV2Geometry(pageStr));
  const canonicalLineIndex = (lineIndex: number) =>
    canonicalizeLineIndex(canonicalLayout, lineIndex);
  body = {
    ...body,
    blob_edits: body.blob_edits?.map((edit) => ({
      ...edit,
      line_index: canonicalLineIndex(edit.line_index),
    })),
    new_bboxes: body.new_bboxes?.map((bbox) => ({
      ...bbox,
      line_index: canonicalLineIndex(bbox.line_index),
    })),
    line_status: body.line_status
      ? { ...body.line_status, line_index: canonicalLineIndex(body.line_status.line_index) }
      : undefined,
    reset_line: body.reset_line
      ? { line_index: canonicalLineIndex(body.reset_line.line_index) }
      : undefined,
  };

  const results: {
    blob_edits: number;
    new_bboxes: string[];
    updated_bboxes: number;
    deleted_bboxes: string[];
    line_status: boolean;
    reset_line: { deleted_edits: number; deleted_unset: number; deleted_new_bboxes: number } | null;
  } = { blob_edits: 0, new_bboxes: [], updated_bboxes: 0, deleted_bboxes: [], line_status: false, reset_line: null };

  if (body.blob_edits) {
    // Read baseline and existing edits for incremental model update
    const pageStr = String(pageInt).padStart(3, "0");
    const baseline = await readInitialBaseline(pageStr);
    const existingEdits = readBlobEdits(pageInt);

    for (const e of body.blob_edits) {
      // --- Incremental model update: compute old/new labels + context ---
      if (baseline && (e.label !== undefined || e.deleted)) {
        const line = baseline.lines.find((l) => l.line_index === e.line_index);
        if (line) {
          const PLACEHOLDER = new Set(["E", "?"]);

          // Build effective labels for the line BEFORE this edit
          const effectiveLabels = line.tokens.map((tok) => {
            const key = `${line.line_index}:${tok.blob_id}`;
            const ed = existingEdits.get(key);
            if (ed?.deleted === 1) return null;
            return ed?.label ?? tok.label ?? null;
          });

          // Find this blob's position in the token array
          const tokIdx = line.tokens.findIndex((t) => String(t.blob_id) === String(e.blob_id));
          if (tokIdx >= 0) {
            const oldLabel = effectiveLabels[tokIdx];
            const newLabel = e.deleted ? null : (e.label ?? oldLabel);

            // Find adjacent non-placeholder, non-deleted labels
            let leftLabel: string | null = null;
            for (let j = tokIdx - 1; j >= 0; j--) {
              const l = effectiveLabels[j];
              if (l && !PLACEHOLDER.has(l)) { leftLabel = l; break; }
            }
            let rightLabel: string | null = null;
            for (let j = tokIdx + 1; j < effectiveLabels.length; j++) {
              const l = effectiveLabels[j];
              if (l && !PLACEHOLDER.has(l)) { rightLabel = l; break; }
            }

            if (oldLabel !== newLabel) {
              applyEditToModel(leftLabel, oldLabel, newLabel, rightLabel);
            }
          }
        }
      }

      upsertBlobEdit({
        page: pageInt,
        line_index: e.line_index,
        blob_id: String(e.blob_id),
        label: e.label !== undefined ? e.label : undefined,
        diacritics: e.diacritics !== undefined ? e.diacritics : undefined,
        lacuna_bracket: e.lacuna_bracket !== undefined ? e.lacuna_bracket : undefined,
        deleted: e.deleted ?? false,
        overline_mark_id: e.overline_mark_id,
        source: e.source,
      });
      results.blob_edits += 1;
    }
  }
  if (body.new_bboxes) {
    // Lazy-load baseline for new bbox model updates
    const pageStr = String(pageInt).padStart(3, "0");
    const baseline = await readInitialBaseline(pageStr);
    const existingEdits = readBlobEdits(pageInt);
    const PLACEHOLDER = new Set(["E", "?"]);

    for (const b of body.new_bboxes) {
      // Model update: new labeled char inserted into the line
      if (b.label && baseline) {
        const line = baseline.lines.find((l) => l.line_index === b.line_index);
        if (line) {
          // Build effective labels with x-positions to find neighbors
          const positioned: { x: number; label: string | null }[] = line.tokens.map((tok) => {
            const key = `${line.line_index}:${tok.blob_id}`;
            const ed = existingEdits.get(key);
            if (ed?.deleted === 1) return { x: tok.geometry?.warped_bbox?.[0] ?? 0, label: null };
            const lbl = ed?.label ?? tok.label ?? null;
            return { x: tok.geometry?.warped_bbox?.[0] ?? 0, label: lbl };
          });
          // Insert new bbox by x-position
          const insertX = b.x0;
          positioned.push({ x: insertX, label: b.label });
          positioned.sort((a, c) => a.x - c.x);

          const insertIdx = positioned.findIndex((p) => p.x === insertX && p.label === b.label);
          let leftLabel: string | null = null;
          for (let j = insertIdx - 1; j >= 0; j--) {
            const l = positioned[j].label;
            if (l && !PLACEHOLDER.has(l)) { leftLabel = l; break; }
          }
          let rightLabel: string | null = null;
          for (let j = insertIdx + 1; j < positioned.length; j++) {
            const l = positioned[j].label;
            if (l && !PLACEHOLDER.has(l)) { rightLabel = l; break; }
          }

          // null→newLabel = insertion
          applyEditToModel(leftLabel, null, b.label, rightLabel);
        }
      }

      const inserted = createNewBbox({
        page: pageInt,
        line_index: b.line_index,
        x0: b.x0,
        y0: b.y0,
        x1: b.x1,
        y1: b.y1,
        coord_space: b.coord_space,
        label: b.label ?? null,
        diacritics: b.diacritics ? JSON.stringify(b.diacritics) : null,
        lacuna_bracket: b.lacuna_bracket ?? null,
        overline_mark_id: null,
        missplit_review_id: null,
      });
      results.new_bboxes.push(inserted.id);
    }
  }
  if (body.update_new_bboxes) {
    // Load context for model updates on relabeled new bboxes
    const pageStr = String(pageInt).padStart(3, "0");
    const baseline = await readInitialBaseline(pageStr);
    const existingEdits = readBlobEdits(pageInt);
    const allNewBboxes = readNewBboxes(pageInt);
    const PLACEHOLDER = new Set(["E", "?"]);

    for (const u of body.update_new_bboxes) {
      // Find the existing new bbox to get old label and position
      const existing = allNewBboxes.find((nb) => nb.id === u.id);
      if (existing && u.label !== undefined && u.label !== existing.label && baseline) {
        const line = baseline.lines.find((l) => l.line_index === existing.line_index);
        if (line) {
          // Build positioned labels including all new bboxes on this line
          const positioned: { x: number; label: string | null }[] = line.tokens.map((tok) => {
            const key = `${line.line_index}:${tok.blob_id}`;
            const ed = existingEdits.get(key);
            if (ed?.deleted === 1) return { x: tok.geometry?.warped_bbox?.[0] ?? 0, label: null };
            return { x: tok.geometry?.warped_bbox?.[0] ?? 0, label: ed?.label ?? tok.label ?? null };
          });
          // Add new bboxes on this line
          for (const nb of allNewBboxes) {
            if (nb.line_index === existing.line_index && nb.label) {
              positioned.push({ x: nb.x0, label: nb.label });
            }
          }
          positioned.sort((a, c) => a.x - c.x);

          const idx = positioned.findIndex((p) => p.x === existing.x0 && p.label === existing.label);
          if (idx >= 0) {
            let leftLabel: string | null = null;
            for (let j = idx - 1; j >= 0; j--) {
              const l = positioned[j].label;
              if (l && !PLACEHOLDER.has(l)) { leftLabel = l; break; }
            }
            let rightLabel: string | null = null;
            for (let j = idx + 1; j < positioned.length; j++) {
              const l = positioned[j].label;
              if (l && !PLACEHOLDER.has(l)) { rightLabel = l; break; }
            }
            applyEditToModel(leftLabel, existing.label, u.label, rightLabel);
          }
        }
      }

      const updated = updateNewBbox(u.id, {
        label: u.label !== undefined ? u.label : undefined,
        diacritics: u.diacritics ? JSON.stringify(u.diacritics) : undefined,
        overline_mark_id: u.overline_mark_id !== undefined ? u.overline_mark_id : undefined,
      });
      if (updated) results.updated_bboxes += 1;
    }
  }
  if (body.delete_new_bboxes) {
    const pageStr = String(pageInt).padStart(3, "0");
    const baseline = await readInitialBaseline(pageStr);
    const existingEdits = readBlobEdits(pageInt);
    const allNewBboxes = readNewBboxes(pageInt);
    const PLACEHOLDER = new Set(["E", "?"]);

    for (const id of body.delete_new_bboxes) {
      // Look up the bbox before deletion for model update
      const target = allNewBboxes.find((nb) => nb.id === id);
      if (target && target.label && baseline) {
        const line = baseline.lines.find((l) => l.line_index === target.line_index);
        if (line) {
          const positioned: { x: number; label: string | null }[] = line.tokens.map((tok) => {
            const key = `${line.line_index}:${tok.blob_id}`;
            const ed = existingEdits.get(key);
            if (ed?.deleted === 1) return { x: tok.geometry?.warped_bbox?.[0] ?? 0, label: null };
            return { x: tok.geometry?.warped_bbox?.[0] ?? 0, label: ed?.label ?? tok.label ?? null };
          });
          for (const nb of allNewBboxes) {
            if (nb.line_index === target.line_index && nb.label) {
              positioned.push({ x: nb.x0, label: nb.label });
            }
          }
          positioned.sort((a, c) => a.x - c.x);

          const idx = positioned.findIndex((p) => p.x === target.x0 && p.label === target.label);
          if (idx >= 0) {
            let leftLabel: string | null = null;
            for (let j = idx - 1; j >= 0; j--) {
              const l = positioned[j].label;
              if (l && !PLACEHOLDER.has(l)) { leftLabel = l; break; }
            }
            let rightLabel: string | null = null;
            for (let j = idx + 1; j < positioned.length; j++) {
              const l = positioned[j].label;
              if (l && !PLACEHOLDER.has(l)) { rightLabel = l; break; }
            }
            // label→null = deletion
            applyEditToModel(leftLabel, target.label, null, rightLabel);
          }
        }
      }

      const removed = deleteNewBbox(id);
      if (removed) results.deleted_bboxes.push(id);
    }
  }
  if (body.line_status) {
    setLineStatus(
      pageInt,
      body.line_status.line_index,
      body.line_status.status,
      body.line_status.note ?? null,
    );
    results.line_status = true;

    // When a line is marked "done" or "special", reinforce all its tokens
    // as confirmed-correct. This trains the model to reduce false positives.
    if (body.line_status.status === "done" || body.line_status.status === "special") {
      const pageStr = String(pageInt).padStart(3, "0");
      const baseline = await readInitialBaseline(pageStr);
      if (baseline) {
        const line = baseline.lines.find((l) => l.line_index === body.line_status!.line_index);
        if (line) {
          const existingEdits = readBlobEdits(pageInt);
          const effectiveLabels = line.tokens.map((tok) => {
            const key = `${line.line_index}:${tok.blob_id}`;
            const ed = existingEdits.get(key);
            if (ed?.deleted === 1) return null;
            return ed?.label ?? tok.label ?? null;
          });
          reinforceConfirmedLine(effectiveLabels);
        }
      }
    }
  }
  if (body.reset_line) {
    results.reset_line = resetLine(pageInt, body.reset_line.line_index);
  }

  // For reset_line, the model needs full invalidation (many edits wiped at once).
  // Normal blob_edits are handled incrementally via applyEditToModel above.
  if (results.reset_line) {
    invalidateModel();
  }

  return NextResponse.json({ ok: true, results });
}
