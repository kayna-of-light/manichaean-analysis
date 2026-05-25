import "server-only";
import type { V2RowGeometry } from "./pipelineReaders";

export interface CanonicalV2Row extends V2RowGeometry {
  display_index: number;
  source_indices: number[];
}

export interface CanonicalLineLayout {
  rows: CanonicalV2Row[];
  canonicalBySourceIndex: Map<number, number>;
  displayByLineIndex: Map<number, number>;
  sourceIndicesByCanonicalIndex: Map<number, number[]>;
  lineIndexes: Set<number>;
}

export function buildCanonicalLineLayout(
  rows: V2RowGeometry[] | null | undefined,
): CanonicalLineLayout | null {
  if (!rows || rows.length === 0) return null;

  const byIndex = new Map<number, CanonicalV2Row>();
  const canonicalBySourceIndex = new Map<number, number>();
  const sourceIndicesByCanonicalIndex = new Map<number, number[]>();
  const mergedAway = new Set<number>();

  for (const row of rows) {
    byIndex.set(row.index, {
      ...row,
      bbox: [...row.bbox] as [number, number, number, number],
      x_span: [...row.x_span] as [number, number],
      display_index: row.index,
      source_indices: [row.index],
    });
    canonicalBySourceIndex.set(row.index, row.index);
    sourceIndicesByCanonicalIndex.set(row.index, [row.index]);
  }

  const markers = rows.filter((row) => row.source === "chapter_marker_row");
  const nonMarkers = rows.filter((row) => row.source !== "chapter_marker_row");
  for (const marker of markers) {
    const neighbor = nearestVerticallyOverlappingRow(marker, nonMarkers);
    if (!neighbor) continue;

    const target = byIndex.get(neighbor.index);
    if (!target) continue;

    mergedAway.add(marker.index);
    canonicalBySourceIndex.set(marker.index, target.index);
    target.bbox = unionBbox(target.bbox, marker.bbox);
    target.x_span = [
      Math.min(target.x_span[0], marker.x_span[0]),
      Math.max(target.x_span[1], marker.x_span[1]),
    ];
    target.source_indices = [...target.source_indices, marker.index].sort((a, b) => a - b);
    sourceIndicesByCanonicalIndex.set(target.index, target.source_indices);
    sourceIndicesByCanonicalIndex.delete(marker.index);
  }

  const canonicalRows = [...byIndex.values()]
    .filter((row) => !mergedAway.has(row.index))
    .sort((a, b) => a.index - b.index)
    .map((row, index) => ({ ...row, display_index: index + 1 }));

  const displayByLineIndex = new Map<number, number>();
  const lineIndexes = new Set<number>();
  for (const row of canonicalRows) {
    displayByLineIndex.set(row.index, row.display_index);
    lineIndexes.add(row.index);
  }

  return {
    rows: canonicalRows,
    canonicalBySourceIndex,
    displayByLineIndex,
    sourceIndicesByCanonicalIndex,
    lineIndexes,
  };
}

export function canonicalizeLineIndex(
  layout: CanonicalLineLayout | null | undefined,
  lineIndex: number,
): number {
  return layout?.canonicalBySourceIndex.get(lineIndex) ?? lineIndex;
}

export function displayIndexForLine(
  layout: CanonicalLineLayout | null | undefined,
  lineIndex: number,
): number {
  return layout?.displayByLineIndex.get(lineIndex) ?? lineIndex;
}

export function sourceIndicesForCanonicalLine(
  layout: CanonicalLineLayout | null | undefined,
  lineIndex: number,
): number[] {
  const canonical = canonicalizeLineIndex(layout, lineIndex);
  return layout?.sourceIndicesByCanonicalIndex.get(canonical) ?? [canonical];
}

function nearestVerticallyOverlappingRow(
  marker: V2RowGeometry,
  candidates: V2RowGeometry[],
): V2RowGeometry | null {
  let best: V2RowGeometry | null = null;
  let bestDistance = Infinity;
  for (const candidate of candidates) {
    const distance = Math.abs(marker.baseline_y - candidate.baseline_y);
    const overlap = verticalOverlap(marker.bbox, candidate.bbox);
    if (overlap <= 0 && distance >= 15) continue;
    if (distance < bestDistance) {
      best = candidate;
      bestDistance = distance;
    }
  }
  return best;
}

function verticalOverlap(
  a: [number, number, number, number],
  b: [number, number, number, number],
): number {
  const top = Math.max(a[1], b[1]);
  const bottom = Math.min(a[1] + a[3], b[1] + b[3]);
  return Math.max(0, bottom - top);
}

function unionBbox(
  a: [number, number, number, number],
  b: [number, number, number, number],
): [number, number, number, number] {
  const x0 = Math.min(a[0], b[0]);
  const y0 = Math.min(a[1], b[1]);
  const x1 = Math.max(a[0] + a[2], b[0] + b[2]);
  const y1 = Math.max(a[1] + a[3], b[1] + b[3]);
  return [x0, y0, x1 - x0, y1 - y0];
}