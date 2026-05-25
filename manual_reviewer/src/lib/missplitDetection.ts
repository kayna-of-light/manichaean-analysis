import "server-only";
import fs from "node:fs";
import path from "node:path";
import { INGEST_DIR } from "./paths";
import { readBlobEdits, readClusterOverridesByIds, readReassignmentsForPage } from "./repo";
import { editIdsForBaselineLine } from "./tokenIdentity";
import { computeUnsplitLineStats, isUnsplit, MIN_HEIGHT_FOR_UNSPLIT, MIN_WH_RATIO_FOR_UNSPLIT, TALL_BLOB_HEIGHT_FACTOR, TALL_BLOB_RATIO_FOR_UNSPLIT } from "./unsplitLogic";

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
        cluster?: string;
        geometry: {
          aabb: [number, number, number, number];
          img_quad: number[][] | null;
        };
      }>;
    }>;

    // Load blob edits once per page to exclude deleted blobs & resolve labels
    const edits = readBlobEdits(pageInt);
    // Load reassignments to determine effective cluster
    const reassignments = readReassignmentsForPage(pageInt);

    // Collect unique cluster IDs for this page to load overrides
    // (include both baseline clusters and reassignment targets)
    const clusterIds = new Set<number>();
    for (const line of lines) {
      for (const t of line.tokens) {
        if (t.cluster) {
          const cid = parseInt(t.cluster, 10);
          if (Number.isFinite(cid)) clusterIds.add(cid);
        }
      }
    }
    for (const r of reassignments.values()) {
      clusterIds.add(r.to_cluster);
    }
    const clusterOverrides = readClusterOverridesByIds([...clusterIds]);

    for (const line of lines) {
      // Build proper edit IDs that handle duplicate blob_ids within a line
      const editIds = editIdsForBaselineLine(line);
      // Filter deleted and resolve effective labels in a single pass
      const activeTokens: typeof line.tokens = [];
      for (let idx = 0; idx < line.tokens.length; idx++) {
        const t = line.tokens[idx];
        const editId = editIds[idx];
        const edit = edits.get(`${line.line_index}:${editId}`)
          ?? (editId !== String(t.blob_id) ? edits.get(`${line.line_index}:${t.blob_id}`) : undefined);
        if (edit?.deleted) continue;
        // Resolve effective label: blob_edit.label > cluster_override(effective_cluster).label > baseline
        let label = t.label;
        if (edit?.label) {
          label = edit.label;
        } else {
          // Determine effective cluster (reassignment overrides baseline)
          const reassign = reassignments.get(`${line.line_index}:${t.blob_id}`);
          const effectiveCluster = reassign
            ? reassign.to_cluster
            : (t.cluster ? parseInt(t.cluster, 10) : NaN);
          if (Number.isFinite(effectiveCluster)) {
            const co = clusterOverrides.get(effectiveCluster);
            if (co?.label) label = co.label;
          }
        }
        activeTokens.push({ ...t, label });
      }
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
 * Uses shared logic from unsplitLogic.ts (also used by LineCanvas.tsx).
 * -------------------------------------------------------------------------- */

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

  const dims = items.map((it) => ({
    width: it.aabb[2] - it.aabb[0],
    height: it.aabb[3] - it.aabb[1],
  }));
  const stats = computeUnsplitLineStats(dims);

  const results: MissplitGroup[] = [];

  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    if (excludeBlobIds?.has(it.blobId)) continue;
    const { width: w, height: h } = dims[i];
    if (!isUnsplit(w, h, stats)) continue;

    results.push({
      page,
      lineIndex,
      blobIds: [it.blobId],
      labels: [it.label],
      aabb: it.aabb,
      blobAabbs: [it.aabb],
      imgQuads: [it.imgQuad],
      medianHeight: stats.medianHeight,
      imageSize,
      type: "undersplit",
    });
  }

  return results;
}

/* --------------------------------------------------------------------------
 * Overlap detection — blobs whose bounding boxes significantly overlap in
 * x-range.  Any overlap is suspicious regardless of relative size — it
 * indicates duplicate OCR, fragmented detection, or stacked bboxes.
 * -------------------------------------------------------------------------- */

const MIN_OVERLAP_RATIO = 0.80; // 80% mutual x-overlap to flag

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

  // Find all pairs where x-overlap is ≥ 80% of EITHER blob's width.
  // Union-find to group transitive overlaps together.
  const parent = new Map<number, number>();
  function find(x: number): number {
    while (parent.has(x) && parent.get(x) !== x) x = parent.get(x)!;
    return x;
  }
  function union(a: number, b: number): void {
    const ra = find(a), rb = find(b);
    if (ra !== rb) parent.set(rb, ra);
  }

  for (let i = 0; i < items.length; i++) {
    const a = items[i];
    const aW = a.aabb[2] - a.aabb[0];
    if (aW <= 0) continue;

    for (let j = i + 1; j < items.length; j++) {
      const b = items[j];
      const bW = b.aabb[2] - b.aabb[0];
      if (bW <= 0) continue;

      const overlapX0 = Math.max(a.aabb[0], b.aabb[0]);
      const overlapX1 = Math.min(a.aabb[2], b.aabb[2]);
      const overlap = Math.max(0, overlapX1 - overlapX0);

      // Flag if overlap covers ≥ 80% of EITHER blob's width
      if (overlap / aW >= MIN_OVERLAP_RATIO || overlap / bW >= MIN_OVERLAP_RATIO) {
        if (!parent.has(a.idx)) parent.set(a.idx, a.idx);
        if (!parent.has(b.idx)) parent.set(b.idx, b.idx);
        union(a.idx, b.idx);
      }
    }
  }

  if (parent.size === 0) return [];

  // Collect groups from union-find
  const groups = new Map<number, number[]>();
  for (const idx of parent.keys()) {
    const root = find(idx);
    const list = groups.get(root) ?? [];
    list.push(idx);
    groups.set(root, list);
  }

  const results: MissplitGroup[] = [];
  const itemByIdx = new Map(items.map((it) => [it.idx, it]));

  for (const [, memberIdxs] of groups) {
    if (memberIdxs.length < 2) continue;
    const groupItems = memberIdxs.map((i) => itemByIdx.get(i)!);

    // Sort by x-center for consistent ordering
    groupItems.sort((a, b) => {
      const aCx = (a.aabb[0] + a.aabb[2]) / 2;
      const bCx = (b.aabb[0] + b.aabb[2]) / 2;
      return aCx - bCx || a.idx - b.idx;
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
