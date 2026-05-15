import type { LineRecord, Token } from "./zodSchemas";
import type { LinesBaseSplit } from "./zodSchemas";

/**
 * Given the per-line `img_quad` (4 corners in page-space, in order
 * top-left, top-right, bottom-right, bottom-left) and a warped-space
 * bbox inside the line strip of dimensions warped_size = [W, H],
 * compute the polygon in page-space.
 *
 * We apply bilinear interpolation over (u, v) ∈ [0,1] across the quad:
 *   p(u,v) = (1-u)(1-v) TL + u(1-v) TR + uv BR + (1-u)v BL
 */
export function bilinear(
  u: number,
  v: number,
  quad: number[][],
): [number, number] {
  const [tl, tr, br, bl] = quad;
  const x =
    (1 - u) * (1 - v) * tl[0] +
    u * (1 - v) * tr[0] +
    u * v * br[0] +
    (1 - u) * v * bl[0];
  const y =
    (1 - u) * (1 - v) * tl[1] +
    u * (1 - v) * tr[1] +
    u * v * br[1] +
    (1 - u) * v * bl[1];
  return [x, y];
}

export interface LineQuadIndex {
  /** Per line_index: union quad covering the entire warped strip. */
  lineQuad: Map<number, number[][]>;
  warpedSize: Map<number, [number, number]>;
}

/**
 * Build a per-line "strip quad" by taking the bounding hull of all blob
 * `img_quad`s in that line and assigning corners by extremes. This is the
 * line's footprint on the page image.
 */
export function buildLineQuadIndex(lines: LinesBaseSplit): LineQuadIndex {
  const lineQuad = new Map<number, number[][]>();
  const warpedSize = new Map<number, [number, number]>();
  for (const line of lines.lines) {
    warpedSize.set(line.line_index, line.warped_size as [number, number]);
    if (!line.blobs.length) continue;
    // collect all corners
    const pts: [number, number][] = [];
    for (const b of line.blobs) {
      if (!b.img_quad) continue;
      for (const c of b.img_quad) pts.push([c[0], c[1]]);
    }
    if (pts.length === 0) continue;
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    const x0 = Math.min(...xs);
    const x1 = Math.max(...xs);
    const y0 = Math.min(...ys);
    const y1 = Math.max(...ys);
    // axis-aligned approximation (correct enough for overlay placement;
    // we use exact img_quad per blob for token bboxes)
    lineQuad.set(line.line_index, [
      [x0, y0],
      [x1, y0],
      [x1, y1],
      [x0, y1],
    ]);
  }
  return { lineQuad, warpedSize };
}

/** Per-blob image-space quad index. */
export function buildBlobQuadIndex(
  lines: LinesBaseSplit,
): Map<string, number[][]> {
  const m = new Map<string, number[][]>();
  for (const line of lines.lines) {
    for (const b of line.blobs) {
      if (b.img_quad) m.set(`${line.line_index}:${b.id}`, b.img_quad);
    }
  }
  return m;
}

/** Convert a warped bbox to a page-space polygon using its containing line quad. */
export function warpedBboxToPagePolygon(
  bbox: [number, number, number, number],
  warpedSize: [number, number],
  lineQuad: number[][],
): number[][] {
  const [w, h] = warpedSize;
  const [x0, y0, x1, y1] = bbox;
  const u0 = x0 / w;
  const u1 = x1 / w;
  const v0 = y0 / h;
  const v1 = y1 / h;
  return [
    bilinear(u0, v0, lineQuad),
    bilinear(u1, v0, lineQuad),
    bilinear(u1, v1, lineQuad),
    bilinear(u0, v1, lineQuad),
  ];
}

/** Same, but axis-aligned bbox (min/max over the quad corners). */
export function warpedBboxToAabb(
  bbox: [number, number, number, number],
  warpedSize: [number, number],
  lineQuad: number[][],
): [number, number, number, number] {
  const poly = warpedBboxToPagePolygon(bbox, warpedSize, lineQuad);
  const xs = poly.map((p) => p[0]);
  const ys = poly.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

export function tokensSorted(record: LineRecord): Token[] {
  return [...record.tokens].sort(
    (a, b) => a.geometry.warped_bbox[0] - b.geometry.warped_bbox[0],
  );
}
