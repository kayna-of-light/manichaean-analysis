import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import {
  createNewBbox,
  deleteNewBbox,
  resetLine,
  setLineStatus,
  updateNewBbox,
  upsertBlobEdit,
} from "@/lib/repo";
import { EditBlobSchema, NewBboxInputSchema } from "@/lib/zodSchemas";

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
      status: z.enum(["pending", "in_progress", "done", "flagged"]),
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

  const results: {
    blob_edits: number;
    new_bboxes: string[];
    updated_bboxes: number;
    deleted_bboxes: string[];
    line_status: boolean;
    reset_line: { deleted_edits: number; deleted_unset: number; deleted_new_bboxes: number } | null;
  } = { blob_edits: 0, new_bboxes: [], updated_bboxes: 0, deleted_bboxes: [], line_status: false, reset_line: null };

  if (body.blob_edits) {
    for (const e of body.blob_edits) {
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
    for (const b of body.new_bboxes) {
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
      });
      results.new_bboxes.push(inserted.id);
    }
  }
  if (body.update_new_bboxes) {
    for (const u of body.update_new_bboxes) {
      const updated = updateNewBbox(u.id, {
        label: u.label !== undefined ? u.label : undefined,
        diacritics: u.diacritics ? JSON.stringify(u.diacritics) : undefined,
        overline_mark_id: u.overline_mark_id !== undefined ? u.overline_mark_id : undefined,
      });
      if (updated) results.updated_bboxes += 1;
    }
  }
  if (body.delete_new_bboxes) {
    for (const id of body.delete_new_bboxes) {
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
  }
  if (body.reset_line) {
    results.reset_line = resetLine(pageInt, body.reset_line.line_index);
  }

  return NextResponse.json({ ok: true, results });
}
