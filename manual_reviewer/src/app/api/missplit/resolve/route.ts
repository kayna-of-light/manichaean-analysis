import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import {
  createNewBbox,
  resolveMissplitAsCorrect,
  resolveMissplitAsFixed,
  revertMissplitReview,
  upsertBlobEdit,
} from "@/lib/repo";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

const ResolveCorrectSchema = z.object({
  action: z.literal("correct"),
  page: z.number().int(),
  lineIndex: z.number().int(),
  blobIds: z.array(z.number().int()),
});

const ResolveFixedSchema = z.object({
  action: z.literal("fixed"),
  page: z.number().int(),
  lineIndex: z.number().int(),
  blobIds: z.array(z.number().int()),
  /** New labels for the replacement boxes */
  newLabels: z.array(z.string()),
  /** New bounding boxes [x0, y0, x1, y1] in image-space coordinates */
  newBboxes: z.array(z.tuple([z.number(), z.number(), z.number(), z.number()])),
});

const BodySchema = z.discriminatedUnion("action", [
  ResolveCorrectSchema,
  ResolveFixedSchema,
]);

/**
 * POST /api/missplit/resolve
 *
 * Resolves a missplit group — either marks as "correct" (false positive)
 * or applies a fix by deleting old blobs and creating new bounding boxes.
 */
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

  if (body.action === "correct") {
    const id = resolveMissplitAsCorrect(body.page, body.lineIndex, body.blobIds);
    return NextResponse.json({ ok: true, reviewId: id });
  }

  // action === "fixed"
  if (body.newLabels.length !== body.newBboxes.length) {
    return NextResponse.json(
      { error: "newLabels and newBboxes must have same length" },
      { status: 400 },
    );
  }

  // Wrap all mutations in a transaction so partial commits can't happen
  const db = getDb();
  const createdIds: string[] = [];
  let reviewId: number;

  const runFix = db.transaction(() => {
    // Step 1: Mark old blobs as deleted
    for (const blobId of body.blobIds) {
      upsertBlobEdit({
        page: body.page,
        line_index: body.lineIndex,
        blob_id: String(blobId),
        label: null,
        deleted: true,
        source: "manual",
      });
    }

    // Step 2: Record the review (do this before bboxes so we have the ID)
    reviewId = resolveMissplitAsFixed(
      body.page,
      body.lineIndex,
      body.blobIds,
      body.newLabels,
    );

    // Step 3: Create new bounding boxes with labels, linked to the review
    for (let i = 0; i < body.newBboxes.length; i++) {
      const [x0, y0, x1, y1] = body.newBboxes[i];
      const label = body.newLabels[i];
      const created = createNewBbox({
        page: body.page,
        line_index: body.lineIndex,
        x0,
        y0,
        x1,
        y1,
        coord_space: "image",
        label,
        diacritics: null,
        lacuna_bracket: null,
        overline_mark_id: null,
        missplit_review_id: reviewId!,
      });
      createdIds.push(created.id);
    }
  });

  runFix();

  return NextResponse.json({ ok: true, reviewId: reviewId!, newBboxIds: createdIds });
}

/**
 * DELETE /api/missplit/resolve?reviewId=N
 *
 * Reverts a missplit review: un-deletes original blobs, removes new bboxes,
 * and deletes the review record. The group will reappear in detection.
 */
export async function DELETE(req: NextRequest) {
  const idParam = req.nextUrl.searchParams.get("reviewId");
  if (!idParam) {
    return NextResponse.json({ error: "reviewId required" }, { status: 400 });
  }
  const reviewId = Number(idParam);
  if (!Number.isFinite(reviewId)) {
    return NextResponse.json({ error: "invalid reviewId" }, { status: 400 });
  }

  const result = revertMissplitReview(reviewId);
  if (!result) {
    return NextResponse.json({ error: "review not found" }, { status: 404 });
  }

  return NextResponse.json({ ok: true, reverted: result });
}
