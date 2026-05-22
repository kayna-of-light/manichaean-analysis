import { NextResponse } from "next/server";
import { detectMissplitGroups } from "@/lib/missplitDetection";
import { readMissplitReviews } from "@/lib/repo";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/missplit
 *
 * Returns all detected missplit groups with their review status,
 * plus any resolved reviews whose blobs are no longer detected
 * (e.g. "fixed" items where old blobs were deleted).
 */
export async function GET() {
  const groups = detectMissplitGroups();
  const reviews = readMissplitReviews();

  // Build lookup: "page:line:blobIds" → review row
  const reviewMap = new Map<string, (typeof reviews)[number]>();
  for (const r of reviews) {
    const key = `${r.page}:${r.line_index}:${r.blob_ids}`;
    reviewMap.set(key, r);
  }

  // Track which reviews were matched to detected groups
  const matchedKeys = new Set<string>();

  const items = groups.map((g) => {
    const key = `${g.page}:${g.lineIndex}:${JSON.stringify(g.blobIds)}`;
    const review = reviewMap.get(key);
    if (review) matchedKeys.add(key);
    return {
      page: g.page,
      lineIndex: g.lineIndex,
      blobIds: g.blobIds,
      labels: g.labels,
      aabb: g.aabb,
      blobAabbs: g.blobAabbs,
      imgQuads: g.imgQuads,
      medianHeight: g.medianHeight,
      imageSize: g.imageSize,
      type: g.type,
      status: review?.status ?? "pending",
      reviewId: review?.id ?? null,
      newLabels: review?.new_labels ? JSON.parse(review.new_labels) : null,
    };
  });

  // Append orphaned reviews (resolved but no longer detected — blobs deleted)
  for (const r of reviews) {
    const key = `${r.page}:${r.line_index}:${r.blob_ids}`;
    if (matchedKeys.has(key)) continue;
    const blobIds: number[] = JSON.parse(r.blob_ids);
    items.push({
      page: r.page,
      lineIndex: r.line_index,
      blobIds,
      labels: blobIds.map(() => "—"),
      aabb: [0, 0, 0, 0] as [number, number, number, number],
      blobAabbs: [],
      imgQuads: [],
      medianHeight: 0,
      imageSize: [945, 1418] as [number, number],
      type: "oversplit" as const,
      status: r.status,
      reviewId: r.id,
      newLabels: r.new_labels ? JSON.parse(r.new_labels) : null,
    });
  }

  // Fetch new_bboxes for fixed items so previews show repaired state
  const db = getDb();
  const allNewBboxes = db
    .prepare(
      "SELECT page, line_index, x0, y0, x1, y1, missplit_review_id FROM new_bboxes ORDER BY page, line_index, id",
    )
    .all() as { page: number; line_index: number; x0: number; y0: number; x1: number; y1: number; missplit_review_id: number | null }[];

  // Group by review_id (for proper FK linkage) and by page:line (for legacy fallback)
  const bboxByReviewId = new Map<number, [number, number, number, number][]>();
  const bboxByLine = new Map<string, typeof allNewBboxes>();
  for (const b of allNewBboxes) {
    if (b.missplit_review_id != null) {
      const list = bboxByReviewId.get(b.missplit_review_id) ?? [];
      list.push([b.x0, b.y0, b.x1, b.y1]);
      bboxByReviewId.set(b.missplit_review_id, list);
    }
    const k = `${b.page}:${b.line_index}`;
    const lineList = bboxByLine.get(k) ?? [];
    lineList.push(b);
    bboxByLine.set(k, lineList);
  }

  // For each fixed item, find its new_bboxes
  const enrichedItems = items.map((item) => {
    if (item.status !== "fixed") return { ...item, newBboxes: null };

    // Try FK linkage first
    if (item.reviewId != null) {
      const linked = bboxByReviewId.get(item.reviewId);
      if (linked && linked.length > 0) {
        // For orphaned items, compute aabb from linked bboxes
        if (item.aabb[2] === 0) {
          const x0 = Math.min(...linked.map((b) => b[0]));
          const y0 = Math.min(...linked.map((b) => b[1]));
          const x1 = Math.max(...linked.map((b) => b[2]));
          const y1 = Math.max(...linked.map((b) => b[3]));
          return { ...item, aabb: [x0, y0, x1, y1], newBboxes: linked };
        }
        return { ...item, newBboxes: linked };
      }
    }

    // Legacy fallback: spatial overlap with item's original aabb
    const k = `${item.page}:${item.lineIndex}`;
    const lineBboxes = bboxByLine.get(k);
    if (!lineBboxes || lineBboxes.length === 0) return { ...item, newBboxes: null };

    const [ax0, ay0, ax1, ay1] = item.aabb;
    const isOrphaned = ax1 === 0 && ay1 === 0;

    // Orphaned items without FK can't be reliably matched — skip preview
    if (isOrphaned) return { ...item, newBboxes: null };

    // Spatial overlap with tolerance — only for non-orphaned items with valid aabb
    const tol = 2;
    const matched = lineBboxes
      .filter((b) => b.missplit_review_id == null)
      .filter((b) => b.x0 < ax1 + tol && b.x1 > ax0 - tol && b.y0 < ay1 + tol && b.y1 > ay0 - tol)
      .map((b) => [b.x0, b.y0, b.x1, b.y1] as [number, number, number, number]);

    if (matched.length === 0) return { ...item, newBboxes: null };
    return { ...item, newBboxes: matched };
  });

  // Summary stats
  const total = enrichedItems.length;
  const pending = enrichedItems.filter((i) => i.status === "pending").length;
  const correct = enrichedItems.filter((i) => i.status === "correct").length;
  const fixed = enrichedItems.filter((i) => i.status === "fixed").length;

  return NextResponse.json({ items: enrichedItems, stats: { total, pending, correct, fixed } });
}
