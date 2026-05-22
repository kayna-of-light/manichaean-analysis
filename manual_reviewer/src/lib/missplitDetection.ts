import "server-only";
import fs from "node:fs";
import path from "node:path";
import { INGEST_DIR } from "./paths";
import { readBlobEdits } from "./repo";
import { editIdsForBaselineLine } from "./tokenIdentity";

/* --------------------------------------------------------------------------
 * Missplit (oversplit) detection — server-side mirror of the LineCanvas logic.
 *
 * A "missplit group" is 2+ consecutive blobs within tight gap (≤ 1.5px)
 * whose width / line_median_height < 0.80. These are vertical slices of a
 * character that should have been one blob.
 * -------------------------------------------------------------------------- */

const MAX_GAP = 1.5;
const MAX_WIDTH_RATIO = 0.80;
const MAX_MARGINAL_RATIO = 0.90;
const MIN_RUN = 2;
const MIN_HEIGHT_FOR_MEDIAN = 8;

export interface MissplitGroup {
  page: number;
  lineIndex: number;
  blobIds: number[];
  labels: string[];
  /** Combined AABB of the group [x0, y0, x1, y1] */
  aabb: [number, number, number, number];
  /** Individual AABBs for each blob */
  blobAabbs: [number, number, number, number][];
  /** Individual img_quads for each blob */
  imgQuads: (number[][] | null)[];
  medianHeight: number;
  /** Source image dimensions [width, height] */
  imageSize: [number, number];
  /** Detection type */
  type: "oversplit" | "undersplit";
}

interface TokenGeometry {
  blobId: number;
  label: string;
  aabb: [number, number, number, number];
  imgQuad: number[][] | null;
}

/**
 * Detect all missplit groups across all pages (or a specific page).
 */
export function detectMissplitGroups(pageFilter?: number): MissplitGroup[] {
  const baselineDir = path.join(INGEST_DIR, "initial_baseline");
  if (!fs.existsSync(baselineDir)) return [];

  const files = fs
    .readdirSync(baselineDir)
    .filter((f) => /^p\d+\.json$/.test(f))
    .sort();

  const allGroups: MissplitGroup[] = [];

  for (const file of files) {
    const pageInt = parseInt(file.replace("p", "").replace(".json", ""), 10);
    if (pageFilter !== undefined && pageInt !== pageFilter) continue;

    const filePath = path.join(baselineDir, file);
    const raw = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    const imageSize: [number, number] = raw.image_size ?? [945, 1418];
    const lines = raw.lines as Array<{
      line_index: number;
      tokens: Array<{
        blob_id: number;
        label: string;
        geometry: {
          aabb: [number, number, number, number];
          img_quad: number[][] | null;
        };
      }>;
    }>;

    // Load blob edits once per page to exclude deleted blobs
    const edits = readBlobEdits(pageInt);

    for (const line of lines) {
      // Build proper edit IDs that handle duplicate blob_ids within a line
      const editIds = editIdsForBaselineLine(line);
      const activeTokens = line.tokens.filter((t, idx) => {
        const editId = editIds[idx];
        const edit = edits.get(`${line.line_index}:${editId}`)
          // Fallback: if edit_id is suffixed (e.g. "2#1") but DB has raw blob_id ("2"),
          // try raw key. Handles edits created by missplit resolve endpoint.
          ?? (editId !== String(t.blob_id) ? edits.get(`${line.line_index}:${t.blob_id}`) : undefined);
        return !edit?.deleted;
      });
      // Overlap detection first (no exclusion) — catches large blobs containing fragments
      const overlapGroups = detectOverlapGroups(pageInt, line.line_index, activeTokens, imageSize);
      const overlapBlobIds = new Set<number>();
      for (const g of overlapGroups) for (const id of g.blobIds) overlapBlobIds.add(id);

      // Gap-based fragment detection — skip blobs already in overlap groups
      const groups = detectGroupsForLine(pageInt, line.line_index, activeTokens, imageSize, overlapBlobIds);

      allGroups.push(...overlapGroups);
      allGroups.push(...groups);

      // Undersplit detection — exclude blobs in either oversplit type
      const oversplitBlobIds = new Set<number>(overlapBlobIds);
      for (const g of groups) for (const id of g.blobIds) oversplitBlobIds.add(id);
      const unsplit = detectUnsplitForLine(pageInt, line.line_index, activeTokens, imageSize, oversplitBlobIds);
      allGroups.push(...unsplit);
    }
  }

  return allGroups;
}

function detectGroupsForLine(
  page: number,
  lineIndex: number,
  tokens: Array<{
    blob_id: number;
    label: string;
    geometry: {
      aabb: [number, number, number, number];
      img_quad: number[][] | null;
    };
  }>,
  imageSize: [number, number],
  excludeBlobIds?: Set<number>,
): MissplitGroup[] {
  // Build token geometry list
  const items: TokenGeometry[] = [];
  for (const t of tokens) {
    if (!t.geometry?.aabb) continue;
    if (excludeBlobIds?.has(t.blob_id)) continue;
    items.push({
      blobId: t.blob_id,
      label: t.label,
      aabb: t.geometry.aabb,
      imgQuad: t.geometry.img_quad,
    });
  }
  if (items.length < 2) return [];

  // Sort by x-center
  items.sort((a, b) => {
    const aCx = (a.aabb[0] + a.aabb[2]) / 2;
    const bCx = (b.aabb[0] + b.aabb[2]) / 2;
    return aCx - bCx;
  });

  // Compute line median height
  const heights = items
    .map((it) => it.aabb[3] - it.aabb[1])
    .filter((h) => h >= MIN_HEIGHT_FOR_MEDIAN);
  heights.sort((a, b) => a - b);
  const medianHeight =
    heights.length > 0 ? heights[Math.floor(heights.length / 2)] : 15;

  // Find tight-gap groups → fragment sub-runs
  // A "fragment" is narrow: width/medianHeight < 0.80
  // An "undersplit" blob is wide: width/height >= threshold
  // A "marginal" blob is between fragment and normal width — it can continue
  // an existing run (like undersplit) but cannot start one.
  // Within a tight group, fragments AND undersplit blobs form the run
  // (they're all pieces of the same character). Only clearly normal blobs break.
  const groups: MissplitGroup[] = [];
  let tightStart = 0;

  for (let i = 1; i <= items.length; i++) {
    const gap =
      i < items.length ? items[i].aabb[0] - items[i - 1].aabb[2] : Infinity;
    if (gap > MAX_GAP) {
      // End of tight group. Find combined sub-runs within [tightStart..i)
      let runStart = -1;
      let fragCount = 0;
      for (let j = tightStart; j < i; j++) {
        const w = items[j].aabb[2] - items[j].aabb[0];
        const h = items[j].aabb[3] - items[j].aabb[1];
        const isFragment = w / medianHeight < MAX_WIDTH_RATIO;
        const isUndersplit = h >= MIN_HEIGHT_FOR_UNSPLIT &&
          (w / h) >= (h > medianHeight * TALL_BLOB_HEIGHT_FACTOR
            ? TALL_BLOB_RATIO_FOR_UNSPLIT
            : MIN_WH_RATIO_FOR_UNSPLIT);
        // Marginal: above fragment threshold but still narrower than median —
        // can extend an active run but cannot start one
        const isMarginal = !isFragment && !isUndersplit &&
          (w / medianHeight < MAX_MARGINAL_RATIO);
        if (isFragment || isUndersplit) {
          if (runStart < 0) { runStart = j; fragCount = 0; }
          if (isFragment) fragCount++;
        } else if (isMarginal) {
          // Marginal blobs can start or continue a run but don't count as
          // fragments — the fragCount >= 1 gate prevents marginal-only runs
          if (runStart < 0) { runStart = j; fragCount = 0; }
        } else {
          // Normal blob breaks the run — emit if we had 2+ members with fragments
          if (runStart >= 0 && j - runStart >= MIN_RUN && fragCount >= 1) {
            groups.push(buildGroup(page, lineIndex, items, runStart, j, medianHeight, imageSize));
          }
          runStart = -1;
          fragCount = 0;
        }
      }
      if (runStart >= 0 && i - runStart >= MIN_RUN && fragCount >= 1) {
        groups.push(buildGroup(page, lineIndex, items, runStart, i, medianHeight, imageSize));
      }
      tightStart = i;
    }
  }

  return groups;
}

function buildGroup(
  page: number,
  lineIndex: number,
  items: TokenGeometry[],
  start: number,
  end: number,
  medianHeight: number,
  imageSize: [number, number],
): MissplitGroup {
  const slice = items.slice(start, end);
  const x0 = Math.min(...slice.map((it) => it.aabb[0]));
  const y0 = Math.min(...slice.map((it) => it.aabb[1]));
  const x1 = Math.max(...slice.map((it) => it.aabb[2]));
  const y1 = Math.max(...slice.map((it) => it.aabb[3]));

  return {
    page,
    lineIndex,
    blobIds: slice.map((it) => it.blobId),
    labels: slice.map((it) => it.label),
    aabb: [x0, y0, x1, y1],
    blobAabbs: slice.map((it) => it.aabb),
    imgQuads: slice.map((it) => it.imgQuad),
    medianHeight,
    imageSize,
    type: "oversplit",
  };
}

/* --------------------------------------------------------------------------
 * Undersplit detection — blobs that are too wide and likely contain multiple
 * characters that should have been separated.
 *
 * Mirrors the logic in LineCanvas.tsx:
 *   width/height >= 1.7 for normal blobs
 *   width/height >= 2.0 for tall blobs (height > 1.7× median)
 * -------------------------------------------------------------------------- */

const MIN_HEIGHT_FOR_UNSPLIT = 10;
const MIN_WH_RATIO_FOR_UNSPLIT = 1.7;
const TALL_BLOB_HEIGHT_FACTOR = 1.7;
const TALL_BLOB_RATIO_FOR_UNSPLIT = 2.0;

function detectUnsplitForLine(
  page: number,
  lineIndex: number,
  tokens: Array<{
    blob_id: number;
    label: string;
    geometry: {
      aabb: [number, number, number, number];
      img_quad: number[][] | null;
    };
  }>,
  imageSize: [number, number],
  excludeBlobIds?: Set<number>,
): MissplitGroup[] {
  const items: TokenGeometry[] = [];
  for (const t of tokens) {
    if (!t.geometry?.aabb) continue;
    items.push({
      blobId: t.blob_id,
      label: t.label,
      aabb: t.geometry.aabb,
      imgQuad: t.geometry.img_quad,
    });
  }
  if (items.length === 0) return [];

  // Compute line median height
  const heights = items
    .map((it) => it.aabb[3] - it.aabb[1])
    .filter((h) => h >= MIN_HEIGHT_FOR_MEDIAN);
  heights.sort((a, b) => a - b);
  const medianHeight =
    heights.length > 0 ? heights[Math.floor(heights.length / 2)] : 15;

  const results: MissplitGroup[] = [];

  for (const it of items) {
    if (excludeBlobIds?.has(it.blobId)) continue;
    const h = it.aabb[3] - it.aabb[1];
    const w = it.aabb[2] - it.aabb[0];
    if (h < MIN_HEIGHT_FOR_UNSPLIT) continue;
    const ratio = w / h;
    const isTall = h > medianHeight * TALL_BLOB_HEIGHT_FACTOR;
    const threshold = isTall ? TALL_BLOB_RATIO_FOR_UNSPLIT : MIN_WH_RATIO_FOR_UNSPLIT;
    if (ratio >= threshold) {
      results.push({
        page,
        lineIndex,
        blobIds: [it.blobId],
        labels: [it.label],
        aabb: it.aabb,
        blobAabbs: [it.aabb],
        imgQuads: [it.imgQuad],
        medianHeight,
        imageSize,
        type: "undersplit",
      });
    }
  }

  return results;
}

/* --------------------------------------------------------------------------
 * Overlap detection — blobs whose bounding boxes are spatially contained
 * within a larger blob.  When multiple small blobs overlap a single large
 * blob, it indicates fragmented OCR that should have been one character.
 * -------------------------------------------------------------------------- */

const MIN_OVERLAP_RATIO = 0.80; // 80% of smaller blob's x-range within larger (matches page)
const MIN_AREA_FACTOR = 1.25; // larger blob must be 1.25× the area of the smaller (matches page)

function detectOverlapGroups(
  page: number,
  lineIndex: number,
  tokens: Array<{
    blob_id: number;
    label: string;
    geometry: {
      aabb: [number, number, number, number];
      img_quad: number[][] | null;
    };
  }>,
  imageSize: [number, number],
): MissplitGroup[] {
  // Build items with unique index (blob_id can repeat within a line)
  const items: (TokenGeometry & { idx: number })[] = [];
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (!t.geometry?.aabb) continue;
    items.push({
      idx: i,
      blobId: t.blob_id,
      label: t.label,
      aabb: t.geometry.aabb,
      imgQuad: t.geometry.img_quad,
    });
  }
  if (items.length < 2) return [];

  // Compute median height for the group metadata
  const heights = items
    .map((it) => it.aabb[3] - it.aabb[1])
    .filter((h) => h >= MIN_HEIGHT_FOR_MEDIAN);
  heights.sort((a, b) => a - b);
  const medianHeight =
    heights.length > 0 ? heights[Math.floor(heights.length / 2)] : 15;

  // Mirror the page-side logic: for each blob, check if any larger blob
  // (area >= 1.25×) covers 80%+ of its x-range. If so, mark the smaller
  // as overlapping with the larger.
  // Build adjacency: which items overlap which larger item
  const overlapParent = new Map<number, number>(); // idx → parent idx

  for (const current of items) {
    const currentW = current.aabb[2] - current.aabb[0];
    const currentH = current.aabb[3] - current.aabb[1];
    const currentArea = currentW * currentH;
    if (currentW <= 0 || currentArea <= 0) continue;

    for (const other of items) {
      if (other.idx === current.idx) continue;
      const otherW = other.aabb[2] - other.aabb[0];
      const otherH = other.aabb[3] - other.aabb[1];
      const otherArea = otherW * otherH;
      if (otherArea <= currentArea * MIN_AREA_FACTOR) continue;

      const overlapX0 = Math.max(current.aabb[0], other.aabb[0]);
      const overlapX1 = Math.min(current.aabb[2], other.aabb[2]);
      const overlap = Math.max(0, overlapX1 - overlapX0);
      if (overlap / currentW >= MIN_OVERLAP_RATIO) {
        overlapParent.set(current.idx, other.idx);
        break;
      }
    }
  }

  if (overlapParent.size === 0) return [];

  // Group by parent: collect all children that point to the same parent
  const parentToChildren = new Map<number, number[]>();
  for (const [childIdx, parentIdx] of overlapParent) {
    const list = parentToChildren.get(parentIdx) ?? [];
    list.push(childIdx);
    parentToChildren.set(parentIdx, list);
  }

  const results: MissplitGroup[] = [];
  const itemByIdx = new Map(items.map((it) => [it.idx, it]));

  for (const [parentIdx, childIdxs] of parentToChildren) {
    const parent = itemByIdx.get(parentIdx)!;
    const children = childIdxs.map((i) => itemByIdx.get(i)!);
    const groupItems = [parent, ...children];

    // Sort by x-center for consistent ordering
    groupItems.sort((a, b) => {
      const aCx = (a.aabb[0] + a.aabb[2]) / 2;
      const bCx = (b.aabb[0] + b.aabb[2]) / 2;
      return aCx - bCx;
    });

    const x0 = Math.min(...groupItems.map((it) => it.aabb[0]));
    const y0 = Math.min(...groupItems.map((it) => it.aabb[1]));
    const x1 = Math.max(...groupItems.map((it) => it.aabb[2]));
    const y1 = Math.max(...groupItems.map((it) => it.aabb[3]));

    results.push({
      page,
      lineIndex,
      blobIds: groupItems.map((it) => it.blobId),
      labels: groupItems.map((it) => it.label),
      aabb: [x0, y0, x1, y1],
      blobAabbs: groupItems.map((it) => it.aabb),
      imgQuads: groupItems.map((it) => it.imgQuad),
      medianHeight,
      imageSize,
      type: "oversplit",
    });
  }

  return results;
}
