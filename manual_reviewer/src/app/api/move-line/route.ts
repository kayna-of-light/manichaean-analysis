import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import {
  createNewBbox,
  moveNewBboxToLine,
  upsertBlobEdit,
} from "@/lib/repo";
import { readInitialBaseline } from "@/lib/pipelineReaders";

export const dynamic = "force-dynamic";

const BodySchema = z.object({
  page: z.number().int(),
  line_index: z.number().int(),
  blob_id: z.union([z.number(), z.string()]),
  direction: z.enum(["up", "down"]),
  is_new_bbox: z.boolean().default(false),
});

export async function POST(req: NextRequest) {
  let body: z.infer<typeof BodySchema>;
  try {
    body = BodySchema.parse(await req.json());
  } catch (err) {
    return NextResponse.json(
      { error: "bad request", detail: (err as Error).message },
      { status: 400 },
    );
  }

  const targetLine = body.direction === "up"
    ? body.line_index - 1
    : body.line_index + 1;

  if (targetLine < 0) {
    return NextResponse.json({ error: "cannot move above line 0" }, { status: 400 });
  }

  // For new_bboxes: just update the line_index
  if (body.is_new_bbox) {
    const result = moveNewBboxToLine(String(body.blob_id), targetLine);
    if (!result) {
      return NextResponse.json({ error: "new_bbox not found" }, { status: 404 });
    }
    return NextResponse.json({ ok: true, new_line_index: targetLine });
  }

  // For baseline tokens: delete from current line, create new_bbox on target line
  const pageStr = String(body.page).padStart(3, "0");
  const baseline = await readInitialBaseline(pageStr);
  if (!baseline) {
    return NextResponse.json({ error: "baseline not found" }, { status: 404 });
  }

  const line = baseline.lines.find((l) => l.line_index === body.line_index);
  if (!line) {
    return NextResponse.json({ error: "line not found" }, { status: 404 });
  }

  const token = line.tokens.find((t) => String(t.blob_id) === String(body.blob_id));
  if (!token) {
    return NextResponse.json({ error: "token not found" }, { status: 404 });
  }

  // Verify target line exists
  const targetLineObj = baseline.lines.find((l) => l.line_index === targetLine);
  if (!targetLineObj) {
    return NextResponse.json({ error: "target line does not exist" }, { status: 400 });
  }

  // Mark the token as deleted on current line
  upsertBlobEdit({
    page: body.page,
    line_index: body.line_index,
    blob_id: String(body.blob_id),
    deleted: true,
    source: "manual",
  });

  // Create a new_bbox on the target line with the same geometry (image coords)
  const bbox = token.geometry.aabb;
  const created = createNewBbox({
    page: body.page,
    line_index: targetLine,
    x0: bbox[0],
    y0: bbox[1],
    x1: bbox[2],
    y1: bbox[3],
    coord_space: "image",
    label: token.label ?? null,
    diacritics: null,
    lacuna_bracket: null,
    overline_mark_id: token.overline_mark_id ?? null,
    missplit_review_id: null,
  });

  return NextResponse.json({
    ok: true,
    new_line_index: targetLine,
    new_bbox_id: created.id,
  });
}
