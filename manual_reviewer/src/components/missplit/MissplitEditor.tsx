"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import UndoIcon from "@mui/icons-material/Undo";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import CheckIcon from "@mui/icons-material/Check";
import { CopticKeyboard } from "@/components/shared/CopticKeyboard";
import type { MissplitItem } from "@/app/missplit/MissplitPageClient";

interface Props {
  item: MissplitItem;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

/**
 * Two-stage editor for fixing oversplit (missplit) groups.
 *
 * Stage 1 — "Split": Click on the image to place vertical split lines.
 *           Each click adds an x-coordinate. The number of boxes = splits + 1.
 *
 * Stage 2 — "Label": Type the correct characters for each box.
 *           The field accepts N graphemes where N = number of boxes.
 *           Only then is Save enabled.
 */
export function MissplitEditor({ item, open, onClose, onSaved }: Props) {
  const [splits, setSplits] = useState<number[]>([]);
  const [labelText, setLabelText] = useState("");
  const [saving, setSaving] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);

  // Compute the crop region for the editor (generous padding for diacritics/overlines)
  const padX = 8;
  const padY = 14;
  const [ax0, ay0, ax1, ay1] = item.aabb;
  const cropX = ax0 - padX;
  const cropY = ay0 - padY;
  const cropW = ax1 - ax0 + padX * 2;
  const cropH = ay1 - ay0 + padY * 2;

  // Scale to display: make the crop large enough to interact with
  const editorHeight = 120;
  const editorScale = editorHeight / cropH;
  const editorWidth = cropW * editorScale;

  const page = String(item.page).padStart(3, "0");
  const imageUrl = `/api/image?root=textbody&p=${encodeURIComponent(`p${page}_text_body.jpg`)}`;
  const [imgW, imgH] = item.imageSize;

  // Sorted split x-coordinates
  const sortedSplits = useMemo(() => [...splits].sort((a, b) => a - b), [splits]);

  // Number of boxes produced
  const boxCount = sortedSplits.length + 1;

  // Segment the graphemes from labelText
  const graphemes = useMemo(() => {
    if (!labelText) return [];
    if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
      const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });
      return [...segmenter.segment(labelText)]
        .map((s) => s.segment)
        .filter((s) => !/^\s+$/u.test(s));
    }
    return [...labelText.normalize("NFC")].filter((ch) => !/^\s+$/u.test(ch));
  }, [labelText]);

  const labelsReady = graphemes.length === boxCount && boxCount >= 1;

  // Compute resulting bounding boxes from splits
  const resultBoxes = useMemo(() => {
    const edges = [ax0, ...sortedSplits, ax1];
    const boxes: [number, number, number, number][] = [];
    for (let i = 0; i < edges.length - 1; i++) {
      boxes.push([edges[i], ay0, edges[i + 1], ay1]);
    }
    return boxes;
  }, [sortedSplits, ax0, ax1, ay0, ay1]);

  // Click handler: convert screen click to image x-coordinate
  const handleSvgClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const pxX = e.clientX - rect.left;
      // Convert to image-space
      const imgX = cropX + pxX / editorScale;
      // Only allow splits within the group AABB
      if (imgX <= ax0 + 1 || imgX >= ax1 - 1) return;
      setSplits((prev) => [...prev, imgX]);
    },
    [cropX, editorScale, ax0, ax1],
  );

  const undoSplit = () => setSplits((prev) => prev.slice(0, -1));
  const resetSplits = () => {
    setSplits([]);
    setLabelText("");
  };

  const handleSave = async () => {
    if (!labelsReady || saving) return;
    setSaving(true);
    try {
      const res = await fetch("/api/missplit/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "fixed",
          page: item.page,
          lineIndex: item.lineIndex,
          blobIds: item.blobIds,
          newLabels: graphemes,
          newBboxes: resultBoxes,
        }),
      });
      if (!res.ok) throw new Error("Save failed");
      onSaved();
    } catch {
      // Allow retry
    } finally {
      setSaving(false);
    }
  };

  const handleDialogKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && labelsReady && !saving) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <Box onKeyDown={handleDialogKeyDown} tabIndex={-1}>
      <DialogTitle sx={{ pb: 1 }}>
        Fix Oversplit — p{page} L{item.lineIndex}
        <Typography variant="caption" sx={{ ml: 2, color: "var(--color-glass-muted)" }}>
          {item.labels.join(" · ")} → {item.blobIds.length} fragments
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ px: 3, pb: 2 }}>
        {/* Stage 1: Interactive split placement */}
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          1. Click to place split lines
        </Typography>
        <Typography variant="caption" sx={{ color: "var(--color-glass-muted)", mb: 1, display: "block" }}>
          Click on the image where character boundaries should be.
          {sortedSplits.length > 0 && ` ${boxCount} boxes defined.`}
        </Typography>

        <Box
          sx={{
            border: "1px solid var(--color-glass-border)",
            borderRadius: 1,
            overflow: "hidden",
            backgroundColor: "#1a1a1a",
            cursor: "crosshair",
            mb: 2,
            display: "inline-block",
          }}
        >
          <svg
            ref={svgRef}
            width={editorWidth}
            height={editorHeight}
            viewBox={`${cropX} ${cropY} ${cropW} ${cropH}`}
            onClick={handleSvgClick}
            style={{ display: "block" }}
          >
            {/* Page image */}
            <image
              href={imageUrl}
              x={0}
              y={0}
              width={imgW}
              height={imgH}
              preserveAspectRatio="none"
              style={{ pointerEvents: "none" }}
            />

            {/* Original blob outlines (dimmed) */}
            {item.blobAabbs.map((bbox, i) => (
              <rect
                key={`orig-${i}`}
                x={bbox[0]}
                y={bbox[1]}
                width={bbox[2] - bbox[0]}
                height={bbox[3] - bbox[1]}
                fill="none"
                stroke="rgba(255,100,50,0.4)"
                strokeWidth={0.6}
                strokeDasharray="2 1"
                vectorEffect="non-scaling-stroke"
              />
            ))}

            {/* Result boxes (green) */}
            {resultBoxes.map((box, i) => (
              <rect
                key={`box-${i}`}
                x={box[0]}
                y={box[1]}
                width={box[2] - box[0]}
                height={box[3] - box[1]}
                fill="rgba(80,200,120,0.08)"
                stroke="rgba(80,200,120,0.8)"
                strokeWidth={1.2}
                vectorEffect="non-scaling-stroke"
              />
            ))}

            {/* Split lines */}
            {sortedSplits.map((sx, i) => (
              <line
                key={`split-${i}`}
                x1={sx}
                y1={cropY}
                x2={sx}
                y2={cropY + cropH}
                stroke="rgba(80,200,120,0.9)"
                strokeWidth={1.5}
                vectorEffect="non-scaling-stroke"
                strokeDasharray="3 2"
              />
            ))}

            {/* Box labels (if provided) */}
            {graphemes.length === boxCount &&
              resultBoxes.map((box, i) => (
                <text
                  key={`lbl-${i}`}
                  x={(box[0] + box[2]) / 2}
                  y={box[3] + 3}
                  textAnchor="middle"
                  fontSize={4}
                  fill="rgba(80,200,120,0.9)"
                  fontFamily="var(--font-coptic, serif)"
                >
                  {graphemes[i]}
                </text>
              ))}
          </svg>
        </Box>

        {/* Split controls */}
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Tooltip title="Undo last split">
            <span>
              <IconButton size="small" onClick={undoSplit} disabled={splits.length === 0}>
                <UndoIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Reset all">
            <span>
              <IconButton size="small" onClick={resetSplits} disabled={splits.length === 0}>
                <RestartAltIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Chip
            label={`${boxCount} box${boxCount !== 1 ? "es" : ""}`}
            size="small"
            variant="outlined"
            sx={{ ml: 1 }}
          />
        </Stack>

        <Divider sx={{ my: 2 }} />

        {/* Stage 2: Label input via Coptic keyboard */}
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          2. Type the correct characters ({boxCount} needed)
        </Typography>

        <CopticKeyboard
          mode="multi"
          value={labelText}
          onChange={setLabelText}
          maxChars={boxCount}
          hideDiacritics={false}
          onCommit={handleSave}
        />

        {graphemes.length > 0 && graphemes.length !== boxCount && (
          <Typography variant="caption" color="error" sx={{ mt: 0.5, display: "block" }}>
            {graphemes.length} entered, {boxCount} needed
          </Typography>
        )}
        {labelsReady && (
          <Typography variant="caption" color="success.main" sx={{ mt: 0.5, display: "block" }}>
            Ready to save
          </Typography>
        )}

        {labelsReady && (
          <Typography
            variant="body2"
            sx={{ mt: 1, fontFamily: "var(--font-coptic, serif)", fontSize: 16 }}
          >
            Result: {graphemes.join(" · ")}
          </Typography>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={saving}>
          Cancel (Esc)
        </Button>
        <Button
          variant="contained"
          startIcon={<CheckIcon />}
          onClick={handleSave}
          disabled={!labelsReady || saving}
        >
          {saving ? "Saving…" : "Save Fix (Enter)"}
        </Button>
      </DialogActions>
      </Box>
    </Dialog>
  );
}
