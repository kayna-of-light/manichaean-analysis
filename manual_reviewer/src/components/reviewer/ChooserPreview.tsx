"use client";

import { useState } from "react";
import { Box, IconButton, Tooltip } from "@mui/material";
import ZoomOutMapIcon from "@mui/icons-material/ZoomOutMap";
import ZoomInMapIcon from "@mui/icons-material/ZoomInMap";
import { MemberCrop } from "@/components/cluster/MemberCrop";

interface Props {
  imageUrl: string;
  imageSize: [number, number] | null;
  aabb: [number, number, number, number] | null;
  /** Height when zoomed to fit. Default 56px. */
  baseHeight?: number;
}

/**
 * Square-ish preview of a single glyph, with a one-step zoom-out button so the
 * neighbouring glyphs become visible. Used in the upper-right of the chooser
 * popovers.
 */
export function ChooserPreview({
  imageUrl,
  imageSize,
  aabb,
  baseHeight = 56,
}: Props) {
  const [zoom, setZoom] = useState<"fit" | "context">("fit");
  if (!imageSize || !aabb) return null;

  const cropH = Math.max(1, aabb[3] - aabb[1]);
  // "context" = one zoom-out step: pad by the glyph's own height so neighbour
  // glyphs and stroke context appear around it.
  const pad = zoom === "fit" ? 4 : Math.max(20, Math.round(cropH));
  const displayHeight = zoom === "fit" ? baseHeight : Math.round(baseHeight * 1.6);

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: 0.25,
      }}
    >
      <MemberCrop
        imageUrl={imageUrl}
        imageSize={imageSize}
        aabb={aabb}
        displayHeight={displayHeight}
        pad={pad}
      />
      <Tooltip
        title={zoom === "fit" ? "Zoom out one step" : "Zoom back to fit"}
      >
        <IconButton
          size="small"
          onClick={() => setZoom((z) => (z === "fit" ? "context" : "fit"))}
          sx={{ p: 0.25 }}
        >
          {zoom === "fit" ? (
            <ZoomOutMapIcon sx={{ fontSize: 14 }} />
          ) : (
            <ZoomInMapIcon sx={{ fontSize: 14 }} />
          )}
        </IconButton>
      </Tooltip>
    </Box>
  );
}
