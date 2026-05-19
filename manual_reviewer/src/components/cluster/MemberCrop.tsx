"use client";

import { Box } from "@mui/material";

interface Props {
  imageUrl: string;
  imageSize: [number, number] | null;
  /** AABB in image-space pixels: [x0, y0, x1, y1]. */
  aabb: [number, number, number, number] | null;
  /** Target display height for the crop. */
  displayHeight?: number;
  /** Maximum display width (px). If the natural width exceeds this, the image
   *  is scaled down proportionally so both dimensions fit. */
  maxDisplayWidth?: number;
  /** Padding around the crop, in source-image pixels. */
  pad?: number;
  outline?: string;
  background?: string;
}

/**
 * Renders a cropped region of a larger image using CSS positioning of the full
 * <img>. No server-side cropping required; the browser caches the underlying
 * text-body image once per page.
 */
export function MemberCrop({
  imageUrl,
  imageSize,
  aabb,
  displayHeight = 56,
  maxDisplayWidth,
  pad = 4,
  outline,
  background = "var(--color-glass-surface)",
}: Props) {
  if (!aabb || !imageSize) {
    return (
      <Box
        sx={{
          width: displayHeight,
          height: displayHeight,
          background,
          borderRadius: 1,
          border: "1px dashed var(--color-glass-border)",
        }}
      />
    );
  }
  const [imgW, imgH] = imageSize;
  const [x0, y0, x1, y1] = aabb;
  const px0 = Math.max(0, x0 - pad);
  const py0 = Math.max(0, y0 - pad);
  const px1 = Math.min(imgW, x1 + pad);
  const py1 = Math.min(imgH, y1 + pad);
  const cropW = Math.max(1, px1 - px0);
  const cropH = Math.max(1, py1 - py0);
  let scale = displayHeight / cropH;
  let dispW = Math.max(8, Math.round(cropW * scale));
  let dispH = displayHeight;
  // If max width is set and the natural width exceeds it, scale down to fit.
  if (maxDisplayWidth && dispW > maxDisplayWidth) {
    scale = maxDisplayWidth / cropW;
    dispW = maxDisplayWidth;
    dispH = Math.max(8, Math.round(cropH * scale));
  }

  return (
    <Box
      sx={{
        width: dispW,
        height: dispH,
        overflow: "hidden",
        position: "relative",
        borderRadius: 1,
        background,
        border: outline ?? "1px solid var(--color-glass-border)",
      }}
    >
      <Box
        component="img"
        src={imageUrl}
        alt="member"
        draggable={false}
        sx={{
          position: "absolute",
          left: 0,
          top: 0,
          width: imgW * scale,
          height: imgH * scale,
          transform: `translate(${-px0 * scale}px, ${-py0 * scale}px)`,
          maxWidth: "none",
          pointerEvents: "none",
          userSelect: "none",
        }}
      />
    </Box>
  );
}
