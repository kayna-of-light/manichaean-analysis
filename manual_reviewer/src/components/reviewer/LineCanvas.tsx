"use client";
import { useEffect, useRef, useState } from "react";
import { Box } from "@mui/material";
import type { ReviewLine, ReviewPage, ReviewToken } from "./hooks";
import { useReviewerStore } from "./store";

interface NewBboxOverlay {
  id: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  label: string | null;
  overline_mark_id?: number | null;
}

interface Props {
  page: ReviewPage;
  line: ReviewLine;
  highlightBlob?: string | number | null;
  onTokenClick: (token: ReviewToken, evt: { clientX: number; clientY: number }) => void;
  drawMode?: boolean;
  onNewBbox?: (bbox: { x0: number; y0: number; x1: number; y1: number }) => void;
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
  const [drag, setDrag] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);

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

  const hiddenBlobIds = new Set<number | string>();
  for (const current of tokenBboxes) {
    if (!current || current.area <= 0) continue;
    for (const other of tokenBboxes) {
      if (!other || other === current || other.area <= current.area * 1.25) continue;
      const overlapW = Math.max(0, Math.min(current.right, other.right) - Math.max(current.left, other.left));
      const overlapH = Math.max(0, Math.min(current.bottom, other.bottom) - Math.max(current.top, other.top));
      const covered = (overlapW * overlapH) / current.area;
      if (covered >= 0.88) {
        hiddenBlobIds.add(current.token.blob_id);
        break;
      }
    }
  }

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
    setDrag({ x0: p[0], y0: p[1], x1: p[0], y1: p[1] });
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!drag) return;
    const p = clientToImage(e.clientX, e.clientY);
    if (!p) return;
    setDrag((d) => (d ? { ...d, x1: p[0], y1: p[1] } : d));
  };
  const onMouseUp = () => {
    if (!drag) return;
    const bbox = {
      x0: Math.min(drag.x0, drag.x1),
      y0: Math.min(drag.y0, drag.y1),
      x1: Math.max(drag.x0, drag.x1),
      y1: Math.max(drag.y0, drag.y1),
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
        {line.tokens.map((t) => {
          if (!t.img_quad) return null;
          if (t.deleted) return null;
          const isHighlight =
            highlightBlob !== null && highlightBlob === t.blob_id;
          const needsReview = t.review || t.user_modified || (t.candidates?.length ?? 0) > 0;
          const qxs = t.img_quad.map((p) => p[0]);
          const qys = t.img_quad.map((p) => p[1]);
          const isHiddenByOverlap = hiddenBlobIds.has(t.blob_id);

          const stroke = isHiddenByOverlap
            ? "rgba(255,0,220,0.95)"
            : t.unset
              ? "rgba(255,99,71,0.8)"
              : t.user_modified
                ? "var(--color-glass-accent)"
                : needsReview
                  ? "rgba(255,200,90,0.8)"
                  : "rgba(100,160,220,0.55)";
          const points = t.img_quad
            .map((p) => `${p[0]},${p[1]}`)
            .join(" ");

          if (isHiddenByOverlap) {
            const cx = (Math.min(...qxs) + Math.max(...qxs)) / 2;
            const cy = (Math.min(...qys) + Math.max(...qys)) / 2;
            return (
              <g key={`${t.line_index}-${t.blob_id}`}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={5}
                  fill="rgba(255,0,220,0.2)"
                  stroke="rgba(255,0,220,0.95)"
                  strokeWidth={2}
                  vectorEffect="non-scaling-stroke"
                  style={{ cursor: "pointer" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onTokenClick(t, { clientX: e.clientX, clientY: e.clientY });
                  }}
                />
                <polygon
                  points={points}
                  fill="rgba(255,0,220,0.35)"
                  stroke="rgba(255,0,220,0.95)"
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

          return (
            <g key={`${t.line_index}-${t.blob_id}`}>
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
        })}
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
      </svg>
    </Box>
  );
}
