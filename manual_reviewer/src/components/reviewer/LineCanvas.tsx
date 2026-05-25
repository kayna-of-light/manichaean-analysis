"use client";
import { useEffect, useRef, useState } from "react";
import { Box } from "@mui/material";
import type { ReviewLine, ReviewPage, ReviewToken } from "./hooks";
import { useReviewerStore } from "./store";
import { computeUnsplitLineStats, isUnsplit } from "@/lib/unsplitLogic";

const LACUNA_DOT_BOX_SIZE = 8;

interface NewBboxOverlay {
  id: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  label: string | null;
  overline_mark_id?: number | null;
}

export interface NewBboxDraft {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  label?: string | null;
  openEditor?: boolean;
}

interface Props {
  page: ReviewPage;
  line: ReviewLine;
  highlightBlob?: string | number | null;
  onTokenClick: (token: ReviewToken, evt: { clientX: number; clientY: number }) => void;
  drawMode?: boolean;
  onNewBbox?: (bbox: NewBboxDraft) => void;
  newBboxes?: NewBboxOverlay[];
  onNewBboxClick?: (nb: NewBboxOverlay, evt: { clientX: number; clientY: number }) => void;
}

/**
 * Renders the body image clipped to one line strip and overlays each
 * token's img_quad. The image and overlays live in the same SVG viewBox
 * so there is only one browser transform between page coordinates and
 * screen pixels.
 */
export function LineCanvas({ page, line, highlightBlob, onTokenClick, drawMode, onNewBbox, newBboxes, onNewBboxClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(900);
  const selectBlob = useReviewerStore((s) => s.selectBlob);
  const [drag, setDrag] = useState<{ x0: number; y0: number; x1: number; y1: number; skipEditor: boolean } | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 900;
      setContainerWidth(w);
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  if (!line.line_quad || !line.warped_size) {
    return (
      <Box
        ref={ref}
        sx={{
          height: 60,
          borderRadius: 1,
          border: "1px dashed var(--color-glass-border)",
          color: "var(--color-glass-muted)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
        }}
      >
        line {line.line_index} — no geometry
      </Box>
    );
  }

  // Compute the strip bbox in page coords from the line quad.
  const xs = line.line_quad.map((p) => p[0]);
  const ys = line.line_quad.map((p) => p[1]);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const y0 = Math.min(...ys);
  const y1 = Math.max(...ys);
  const stripW = x1 - x0;
  const stripH = y1 - y0;
  if (stripW <= 0 || stripH <= 0) return null;

  // Scale strip to fill container width. Margins are baked into line_quad
  // by the API so both LineCanvas and TokenStrip share the same x-extent.
  const scale = containerWidth / stripW;
  const pageW = page.image_size[0];
  const pageH = page.image_size[1];

  const tokenId = (token: ReviewToken) => token.edit_id ?? String(token.blob_id);

  const tokenBboxes = line.tokens.map((t) => {
    if (!t.img_quad || t.deleted) return null;
    const qxs = t.img_quad.map((p) => p[0]);
    const qys = t.img_quad.map((p) => p[1]);
    const left = Math.min(...qxs);
    const top = Math.min(...qys);
    const right = Math.max(...qxs);
    const bottom = Math.max(...qys);
    return {
      token: t,
      left,
      top,
      right,
      bottom,
      width: right - left,
      height: bottom - top,
      area: Math.max((right - left) * (bottom - top), 0),
    };
  });

  const visibleTokenBboxes = tokenBboxes.filter(
    (bbox): bbox is NonNullable<(typeof tokenBboxes)[number]> => bbox !== null,
  );

  const minorOverlapBlobIds = new Set<string>();
  for (const current of visibleTokenBboxes) {
    if (current.width <= 0 || current.area <= 0) continue;
    for (const other of visibleTokenBboxes) {
      if (other === current || other.area <= current.area * 1.25) continue;
      const overlapW = Math.max(0, Math.min(current.right, other.right) - Math.max(current.left, other.left));
      const xCoverage = overlapW / current.width;
      if (xCoverage >= 0.8) {
        minorOverlapBlobIds.add(tokenId(current.token));
        break;
      }
    }
  }

  // Detect likely unsplit blobs using shared logic (also used by missplitDetection.ts).
  const unsplitBlobIds = new Set<string>();

  const unsplitDims = visibleTokenBboxes.map((b) => ({
    width: b.width,
    height: b.height,
  }));
  const unsplitStats = computeUnsplitLineStats(unsplitDims);
  const medianHeight = unsplitStats.medianHeight;

  for (const bbox of visibleTokenBboxes) {
    if (isUnsplit(bbox.width, bbox.height, unsplitStats)) {
      unsplitBlobIds.add(tokenId(bbox.token));
    }
  }

  // Detect likely oversplit blobs: consecutive narrow blobs packed at
  // minimum gap. "Narrow" = width / line_median_height < 0.80. This is
  // scale-invariant (both scale together on resize) and correctly excludes
  // tall chars like ⲕ/ϥ whose own w/h is low only because of descenders.
  // Fragments are vertical slices of a character — narrow relative to the
  // LINE, not relative to their own height. Two or more such fragments
  // at minimum gap signals oversplit.
  const MAX_GAP_FOR_OVERSPLIT = 1.5;
  const MAX_WIDTH_RATIO_FOR_FRAGMENT = 0.80; // width / line_median_height
  const missplitBlobIds = new Set<string>();

  // Sort visible blobs by x-center position within the line
  const sortedByX = [...visibleTokenBboxes].sort((a, b) => {
    const aCx = (a.left + a.right) / 2;
    const bCx = (b.left + b.right) / 2;
    return aCx - bCx;
  });

  // Find tight-gap groups, then flag runs of 2+ fragments/undersplit within them
  // Within a tight group, both fragments AND undersplit blobs form the run
  // (they're all pieces of the same character). Only normal-width blobs break.
  let tightStart = 0;
  for (let i = 1; i <= sortedByX.length; i++) {
    const gap = i < sortedByX.length
      ? sortedByX[i].left - sortedByX[i - 1].right
      : Infinity;
    if (gap > MAX_GAP_FOR_OVERSPLIT) {
      // End of a tight group [tightStart..i). Find combined sub-runs.
      let runStart = -1;
      let fragCount = 0;
      for (let j = tightStart; j < i; j++) {
        const isFragment = sortedByX[j].width / medianHeight < MAX_WIDTH_RATIO_FOR_FRAGMENT;
        const isUndersplit = unsplitBlobIds.has(tokenId(sortedByX[j].token));
        if (isFragment || isUndersplit) {
          if (runStart < 0) { runStart = j; fragCount = 0; }
          if (isFragment) fragCount++;
        } else {
          // Normal blob breaks the run
          if (runStart >= 0 && j - runStart >= 2 && fragCount >= 1) {
            for (let k = runStart; k < j; k++) {
              missplitBlobIds.add(tokenId(sortedByX[k].token));
            }
          }
          runStart = -1;
          fragCount = 0;
        }
      }
      // Close any trailing run
      if (runStart >= 0 && i - runStart >= 2 && fragCount >= 1) {
        for (let k = runStart; k < i; k++) {
          missplitBlobIds.add(tokenId(sortedByX[k].token));
        }
      }
      tightStart = i;
    }
  }

  const baseTokenBboxes = [...visibleTokenBboxes]
    .filter((bbox) => !minorOverlapBlobIds.has(tokenId(bbox.token)) && !unsplitBlobIds.has(tokenId(bbox.token)) && !missplitBlobIds.has(tokenId(bbox.token)))
    .sort((a, b) => b.area - a.area);
  const minorOverlapTokenBboxes = [...visibleTokenBboxes]
    .filter((bbox) => minorOverlapBlobIds.has(tokenId(bbox.token)))
    .sort((a, b) => b.area - a.area);
  const unsplitTokenBboxes = [...visibleTokenBboxes]
    .filter((bbox) => unsplitBlobIds.has(tokenId(bbox.token)) && !missplitBlobIds.has(tokenId(bbox.token)))
    .sort((a, b) => b.area - a.area);
  const missplitTokenBboxes = [...visibleTokenBboxes]
    .filter((bbox) => missplitBlobIds.has(tokenId(bbox.token)))
    .sort((a, b) => b.area - a.area);

  const renderTokenOverlay = (
    t: ReviewToken,
    variant: "base" | "minor-overlap" | "unsplit" | "missplit",
  ) => {
    const isHighlight =
      highlightBlob !== null && String(highlightBlob) === tokenId(t);
    const needsReview = t.review || t.user_modified || (t.candidates?.length ?? 0) > 0;
    const qxs = t.img_quad?.map((p) => p[0]) ?? [];
    const qys = t.img_quad?.map((p) => p[1]) ?? [];

    const stroke = variant === "minor-overlap"
      ? "var(--color-review-minor-overlap)"
      : variant === "unsplit"
        ? "var(--color-review-unsplit)"
        : variant === "missplit"
          ? "var(--color-review-missplit)"
          : t.unset
            ? "rgba(255,99,71,0.8)"
            : t.user_modified
              ? "var(--color-glass-accent)"
              : needsReview
                ? "rgba(255,200,90,0.8)"
                : "rgba(100,160,220,0.55)";
    const points = t.img_quad
      ?.map((p) => `${p[0]},${p[1]}`)
      .join(" ") ?? "";
    const key = `${t.line_index}-${t.v1_line_index ?? 0}-${tokenId(t)}`;

    if (variant === "minor-overlap") {
      return (
        <g
          key={key}
          data-overlap-treatment="minor-x-overlap"
          data-line-index={t.line_index}
          data-token-id={tokenId(t)}
        >
          <polygon
            points={points}
            fill="var(--color-review-minor-overlap-fill)"
            stroke="var(--color-review-minor-overlap)"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
            style={{ cursor: "pointer" }}
            onClick={(e) => {
              e.stopPropagation();
              onTokenClick(t, { clientX: e.clientX, clientY: e.clientY });
            }}
          />
        </g>
      );
    }

    if (variant === "unsplit") {
      return (
        <g
          key={key}
          data-quality-issue="unsplit-blob"
          data-line-index={t.line_index}
          data-token-id={tokenId(t)}
        >
          <polygon
            points={points}
            fill="var(--color-review-unsplit-fill)"
            stroke="var(--color-review-unsplit)"
            strokeWidth={1.8}
            strokeDasharray="4 2"
            vectorEffect="non-scaling-stroke"
            style={{ cursor: "pointer" }}
            onClick={(e) => {
              e.stopPropagation();
              onTokenClick(t, { clientX: e.clientX, clientY: e.clientY });
            }}
          />
        </g>
      );
    }

    if (variant === "missplit") {
      return (
        <g
          key={key}
          data-quality-issue="missplit-blob"
          data-line-index={t.line_index}
          data-token-id={tokenId(t)}
        >
          <polygon
            points={points}
            fill="var(--color-review-missplit-fill)"
            stroke="var(--color-review-missplit)"
            strokeWidth={1.5}
            strokeDasharray="2 2"
            vectorEffect="non-scaling-stroke"
            style={{ cursor: "pointer" }}
            onClick={(e) => {
              e.stopPropagation();
              onTokenClick(t, { clientX: e.clientX, clientY: e.clientY });
            }}
          />
        </g>
      );
    }

    return (
      <g key={key}>
        <polygon
          points={points}
          fill={isHighlight ? "rgba(200,164,101,0.18)" : "rgba(0,0,0,0)"}
          stroke={stroke}
          strokeWidth={isHighlight ? 1.6 : 0.8}
          vectorEffect="non-scaling-stroke"
          style={{ cursor: "pointer" }}
          onClick={(e) => {
            e.stopPropagation();
            onTokenClick(t, { clientX: e.clientX, clientY: e.clientY });
          }}
        />
      </g>
    );
  };

  const clientToImage = (clientX: number, clientY: number) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return null;
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    return [x0 + px / scale, y0 + py / scale] as [number, number];
  };

  const onMouseDown = (e: React.MouseEvent) => {
    if (!drawMode) return;
    const p = clientToImage(e.clientX, e.clientY);
    if (!p) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.ctrlKey) {
      const half = LACUNA_DOT_BOX_SIZE / 2;
      setDrag(null);
      onNewBbox?.({
        x0: p[0] - half,
        y0: p[1] - half,
        x1: p[0] + half,
        y1: p[1] + half,
        label: ".",
        openEditor: false,
      });
      return;
    }
    setDrag({ x0: p[0], y0: p[1], x1: p[0], y1: p[1], skipEditor: e.shiftKey });
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!drag) return;
    const p = clientToImage(e.clientX, e.clientY);
    if (!p) return;
    setDrag((d) => (d ? { ...d, x1: p[0], y1: p[1] } : d));
  };
  const onMouseUp = (e: React.MouseEvent) => {
    if (!drag) return;
    const skipEditor = drag.skipEditor || e.shiftKey;
    const bbox = {
      x0: Math.min(drag.x0, drag.x1),
      y0: Math.min(drag.y0, drag.y1),
      x1: Math.max(drag.x0, drag.x1),
      y1: Math.max(drag.y0, drag.y1),
      ...(skipEditor ? { label: "", openEditor: false } : {}),
    };
    setDrag(null);
    if (bbox.x1 - bbox.x0 > 2 && bbox.y1 - bbox.y0 > 2 && onNewBbox) {
      onNewBbox(bbox);
    }
  };

  return (
    <Box
      ref={ref}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={() => setDrag(null)}
      sx={{
        position: "relative",
        width: "100%",
        height: stripH * scale,
        borderRadius: 1,
        overflow: "hidden",
        backgroundColor: "var(--color-glass-surface)",
        cursor: drawMode ? "crosshair" : "default",
        outline: drawMode ? "2px dashed var(--color-glass-accent)" : undefined,
        outlineOffset: -2,
      }}
      onClick={() => selectBlob(line.line_index, null)}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`${x0} ${y0} ${stripW} ${stripH}`}
        preserveAspectRatio="none"
        style={{ position: "absolute", inset: 0, pointerEvents: drawMode ? "none" : undefined }}
      >
        <image
          href={page.image_url}
          x={0}
          y={0}
          width={pageW}
          height={pageH}
          preserveAspectRatio="none"
          style={{ pointerEvents: "none" }}
        />
        {baseTokenBboxes.map((bbox) => renderTokenOverlay(bbox.token, "base"))}
        {newBboxes?.map((nb) => (
          <rect
            key={nb.id}
            x={nb.x0}
            y={nb.y0}
            width={nb.x1 - nb.x0}
            height={nb.y1 - nb.y0}
            fill="rgba(80,200,120,0.15)"
            stroke="rgba(80,200,120,0.9)"
            strokeWidth={1.2}
            vectorEffect="non-scaling-stroke"
            style={{ cursor: "pointer" }}
            onClick={(e) => {
              e.stopPropagation();
              onNewBboxClick?.(nb, { clientX: e.clientX, clientY: e.clientY });
            }}
          />
        ))}
        {minorOverlapTokenBboxes.map((bbox) => renderTokenOverlay(bbox.token, "minor-overlap"))}
        {unsplitTokenBboxes.map((bbox) => renderTokenOverlay(bbox.token, "unsplit"))}
        {missplitTokenBboxes.map((bbox) => renderTokenOverlay(bbox.token, "missplit"))}
        {drag && (
          <rect
            x={Math.min(drag.x0, drag.x1)}
            y={Math.min(drag.y0, drag.y1)}
            width={Math.abs(drag.x1 - drag.x0)}
            height={Math.abs(drag.y1 - drag.y0)}
            fill="rgba(200,164,101,0.2)"
            stroke="var(--color-glass-accent)"
            strokeWidth={1.2}
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
    </Box>
  );
}
