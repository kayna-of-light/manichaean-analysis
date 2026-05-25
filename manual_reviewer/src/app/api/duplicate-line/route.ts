import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import {
  createLineDuplicate,
  createNewBbox,
  readLineDuplicateByLine,
  readLineDuplicates,
  readLineStatuses,
  readNewBboxes,
} from "@/lib/repo";
import { readInitialBaseline, readV2Geometry } from "@/lib/pipelineReaders";
import { buildCanonicalLineLayout, canonicalizeLineIndex } from "@/lib/canonicalLines";

export const dynamic = "force-dynamic";

const DuplicateBboxSchema = z.object({
  x0: z.number().finite(),
  y0: z.number().finite(),
  x1: z.number().finite(),
  y1: z.number().finite(),
  coord_space: z.enum(["warped", "image"]).default("image"),
  kind: z.enum(["base", "lacuna_dot", "mark"]).nullable().optional(),
  label: z.string().nullable().optional(),
  diacritics: z.array(z.string()).nullable().optional(),
  lacuna_bracket: z.string().nullable().optional(),
  overline_mark_id: z.number().int().nullable().optional(),
});

const BodySchema = z.object({
  page: z.number().int(),
  source_line_index: z.number().int(),
  bboxes: z.array(DuplicateBboxSchema).default([]),
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

  const page = String(body.page).padStart(3, "0");
  const baseline = await readInitialBaseline(page);
  if (!baseline) {
    return NextResponse.json({ error: "page not found" }, { status: 404 });
  }

  const canonicalLayout = buildCanonicalLineLayout(await readV2Geometry(page));
  const duplicateSource = readLineDuplicateByLine(body.page, body.source_line_index);
  const sourceLineIndex = duplicateSource?.source_line_index
    ?? canonicalizeLineIndex(canonicalLayout, body.source_line_index);

  const usedLineIndices = new Set<number>();
  if (canonicalLayout) {
    for (const lineIndex of canonicalLayout.lineIndexes) usedLineIndices.add(lineIndex);
  } else {
    for (const line of baseline.lines) usedLineIndices.add(line.line_index);
  }
  for (const duplicate of readLineDuplicates(body.page)) usedLineIndices.add(duplicate.line_index);
  for (const bbox of readNewBboxes(body.page)) usedLineIndices.add(bbox.line_index);
  for (const lineIndex of readLineStatuses(body.page).keys()) usedLineIndices.add(lineIndex);

  if (!usedLineIndices.has(sourceLineIndex)) {
    return NextResponse.json({ error: "source line not found" }, { status: 404 });
  }

  const existingDuplicates = readLineDuplicates(body.page)
    .filter((duplicate) => duplicate.source_line_index === sourceLineIndex);
  const ordinal = Math.max(0, ...existingDuplicates.map((duplicate) => duplicate.ordinal)) + 1;
  const lineIndex = Math.max(0, ...usedLineIndices) + 1;

  const duplicate = createLineDuplicate({
    page: body.page,
    source_line_index: sourceLineIndex,
    line_index: lineIndex,
    ordinal,
  });

  const createdBboxIds = body.bboxes.map((bbox) => {
    const created = createNewBbox({
      page: body.page,
      line_index: duplicate.line_index,
      x0: bbox.x0,
      y0: bbox.y0,
      x1: bbox.x1,
      y1: bbox.y1,
      coord_space: bbox.coord_space,
      kind: bbox.kind ?? "base",
      label: bbox.label ?? null,
      diacritics: bbox.diacritics && bbox.diacritics.length > 0
        ? JSON.stringify(bbox.diacritics)
        : null,
      lacuna_bracket: bbox.lacuna_bracket ?? null,
      overline_mark_id: bbox.overline_mark_id ?? null,
      missplit_review_id: null,
    });
    return created.id;
  });

  return NextResponse.json({
    ok: true,
    duplicate_line_index: duplicate.line_index,
    source_line_index: duplicate.source_line_index,
    ordinal: duplicate.ordinal,
    new_bbox_ids: createdBboxIds,
  });
}