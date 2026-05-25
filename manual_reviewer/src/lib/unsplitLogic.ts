/**
 * Shared undersplit detection logic — used by both:
 *   - missplitDetection.ts (server-side, for the /api/missplit endpoint)
 *   - LineCanvas.tsx (client-side, for the visual overlay)
 *
 * No "server-only" or browser-only imports allowed here.
 */

/* ---- Constants ---- */

/** Minimum blob height to even consider for undersplit */
export const MIN_HEIGHT_FOR_UNSPLIT = 10;

/** Minimum height to include in median calculations (filters dots/noise) */
export const MIN_HEIGHT_FOR_MEDIAN = 8;

/** w/h ratio threshold for normal blobs */
export const MIN_WH_RATIO_FOR_UNSPLIT = 1.7;

/** If blob height > TALL_BLOB_HEIGHT_FACTOR × medianHeight, use stricter ratio */
export const TALL_BLOB_HEIGHT_FACTOR = 1.7;

/** w/h ratio threshold for tall blobs */
export const TALL_BLOB_RATIO_FOR_UNSPLIT = 2.0;

/** Minimum absolute width (image px) to trigger width-relative check */
export const MIN_ABSOLUTE_WIDTH_FOR_UNSPLIT = 28;

/** Blob must be > this × lineMedianWidth to fail width-relative check */
export const MIN_WIDTH_VS_LINE_MEDIAN = 2.0;

/** Need at least this many qualifying blobs to compute a reliable median width */
export const MIN_BLOBS_FOR_WIDTH_CHECK = 5;

/* ---- Types ---- */

export interface UnsplitLineStats {
  medianHeight: number;
  /** 0 means width-relative check is disabled (too few samples) */
  medianWidth: number;
}

/* ---- Functions ---- */

/**
 * Compute line-level statistics needed for undersplit detection.
 * Pass all blob dimensions on the line (including ones that will be excluded later).
 */
export function computeUnsplitLineStats(
  items: { width: number; height: number }[],
): UnsplitLineStats {
  const heights = items
    .map((it) => it.height)
    .filter((h) => h >= MIN_HEIGHT_FOR_MEDIAN);
  heights.sort((a, b) => a - b);
  const medianHeight =
    heights.length > 0 ? heights[Math.floor(heights.length / 2)] : 15;

  const widths = items
    .map((it) => it.width)
    .filter((w) => w >= MIN_HEIGHT_FOR_MEDIAN);
  widths.sort((a, b) => a - b);
  const medianWidth =
    widths.length >= MIN_BLOBS_FOR_WIDTH_CHECK
      ? widths[Math.floor(widths.length / 2)]
      : 0;

  return { medianHeight, medianWidth };
}

/**
 * Determine whether a single blob is undersplit given its dimensions
 * and the line-level stats.
 */
export function isUnsplit(
  width: number,
  height: number,
  stats: UnsplitLineStats,
): boolean {
  if (height < MIN_HEIGHT_FOR_UNSPLIT) return false;

  // Check 1: aspect ratio — catches blobs wider than tall
  const ratio = width / height;
  const isTall = height > stats.medianHeight * TALL_BLOB_HEIGHT_FACTOR;
  const threshold = isTall
    ? TALL_BLOB_RATIO_FOR_UNSPLIT
    : MIN_WH_RATIO_FOR_UNSPLIT;
  if (ratio >= threshold) return true;

  // Check 2: width-relative — catches blobs much wider than line peers
  // (e.g. two tall chars stuck together whose aspect ratio looks normal)
  if (
    stats.medianWidth > 0 &&
    width >= MIN_ABSOLUTE_WIDTH_FOR_UNSPLIT &&
    width > MIN_WIDTH_VS_LINE_MEDIAN * stats.medianWidth
  ) {
    return true;
  }

  return false;
}
