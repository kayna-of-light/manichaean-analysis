"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
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
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlinedIcon from "@mui/icons-material/DeleteOutlined";
import DrawIcon from "@mui/icons-material/Draw";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import SelectAllIcon from "@mui/icons-material/SelectAll";
import TextFieldsIcon from "@mui/icons-material/TextFields";
import { CopticKeyboard } from "@/components/shared/CopticKeyboard";
import {
  useLineEditorData,
  type EditMutationPayload,
  type LineEditorBox,
  type ReviewLine,
  type ReviewPage,
  type useEditMutation,
} from "./hooks";

/* ─── Types ──────────────────────────────────────────────────────────── */

type LocalSource = LineEditorBox["source"] | "drawn";

interface EditableBox extends Omit<LineEditorBox, "source"> {
  source: LocalSource;
  /** Whether user selected this proposal for addition */
  selected: boolean;
}

interface Props {
  open: boolean;
  page: ReviewPage;
  line: ReviewLine | null;
  onClose: () => void;
  mutateEdit: ReturnType<typeof useEditMutation>["mutate"];
  editPending: boolean;
}

type DragState =
  | { kind: "draw"; startX: number; startY: number; x: number; y: number }
  | { kind: "move"; id: string; offsetX: number; offsetY: number; width: number; height: number }
  | { kind: "resize"; id: string; corner: "nw" | "ne" | "sw" | "se" };

const MIN_BOX_SIZE = 3;
const LACUNA_DOT_BOX_SIZE = 8;

/* ─── Geometry helpers ───────────────────────────────────────────────── */

function normalizeBox<T extends { x0: number; y0: number; x1: number; y1: number }>(box: T): T {
  return {
    ...box,
    x0: Math.min(box.x0, box.x1),
    y0: Math.min(box.y0, box.y1),
    x1: Math.max(box.x0, box.x1),
    y1: Math.max(box.y0, box.y1),
  };
}

function boxWidth(b: { x0: number; x1: number }) { return Math.abs(b.x1 - b.x0); }
function boxHeight(b: { y0: number; y1: number }) { return Math.abs(b.y1 - b.y0); }
function boxCenterX(b: { x0: number; x1: number }) { return (b.x0 + b.x1) / 2; }

function toEditable(box: LineEditorBox, selected: boolean): EditableBox {
  return { ...normalizeBox(box), label: box.label ?? null, selected };
}

function drawnBoxId(lineIndex: number) {
  return `drawn_l${lineIndex}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
}

/* ─── Visual helpers ─────────────────────────────────────────────────── */

function boxStroke(box: EditableBox, isFocused: boolean, isProposal: boolean) {
  if (isFocused) return "var(--color-glass-accent)";
  if (isProposal && !box.selected) return "rgba(100,160,255,0.35)";
  if (isProposal && box.selected) return "rgba(100,200,255,0.85)";
  if (box.kind === "lacuna_dot") return "var(--color-status-progress)";
  if (box.kind === "mark") return "var(--color-glass-muted)";
  if (box.source === "existing") return "var(--color-status-done)";
  return "var(--color-status-progress)";
}

function displayLabel(lbl: string | null): string {
  if (!lbl) return "—";
  if (lbl === "." || lbl === "_lacuna_dot") return "·";
  if (lbl.startsWith("_")) return "?";
  return lbl;
}

/* ─── Main Component ─────────────────────────────────────────────────── */

export function LineEditorDialog({ open, page, line, onClose, mutateEdit, editPending }: Props) {
  const lineIndex = line?.line_index ?? null;
  const { data, isFetching, error } = useLineEditorData(page.page, lineIndex, open && lineIndex != null);
  const frameRef = useRef<HTMLDivElement>(null);
  const [frameWidth, setFrameWidth] = useState(900);

  // Core state
  const [existingBoxes, setExistingBoxes] = useState<EditableBox[]>([]);
  const [proposals, setProposals] = useState<EditableBox[]>([]);
  const [generated, setGenerated] = useState(false);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState(false);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [deletedExistingIds, setDeletedExistingIds] = useState<Set<string>>(new Set());
  const [replaceExistingBoxes, setReplaceExistingBoxes] = useState(false);

  // Resize observer
  useEffect(() => {
    if (!frameRef.current) return;
    const observer = new ResizeObserver((entries) => {
      setFrameWidth(entries[0]?.contentRect.width ?? 900);
    });
    observer.observe(frameRef.current);
    return () => observer.disconnect();
  }, []);

  // Initialize from API data
  useEffect(() => {
    if (!open || !data) return;
    const existing = data.existing_bboxes.map((b) => toEditable(b, true));
    setExistingBoxes(existing);
    setProposals([]);
    setGenerated(false);
    setFocusedId(null);
    setDrawMode(false);
    setDrag(null);
    setDeletedExistingIds(new Set());
    setReplaceExistingBoxes(false);
  }, [data, open]);

  // Viewport — generous padding to show edge characters in context
  const view = useMemo(() => {
    if (!data) return null;
    const [x, y, width, height] = data.preview_bbox;
    return { x, y, width: Math.max(1, width), height: Math.max(1, height) };
  }, [data]);

  const scale = view ? frameWidth / view.width : 1;

  const clientToImage = useCallback((clientX: number, clientY: number) => {
    const rect = frameRef.current?.getBoundingClientRect();
    if (!rect || !view) return null;
    return { x: view.x + (clientX - rect.left) / scale, y: view.y + (clientY - rect.top) / scale };
  }, [view, scale]);

  /* ─── Derived state ────────────────────────────────────────── */

  const allBoxes = useMemo(() => [...existingBoxes, ...proposals], [existingBoxes, proposals]);
  const focusedBox = allBoxes.find((b) => b.id === focusedId) ?? null;
  const isProposal = useCallback((id: string) => proposals.some((p) => p.id === id), [proposals]);
  const selectedProposals = useMemo(() => proposals.filter((p) => p.selected), [proposals]);
  const activeExistingBoxes = useMemo(
    () => existingBoxes.filter((b) => !deletedExistingIds.has(b.id)),
    [existingBoxes, deletedExistingIds],
  );
  const replaceLineIndices = useMemo(() => {
    if (data) return data.source_indices.length ? data.source_indices : [data.line_index];
    return lineIndex == null ? [] : [lineIndex];
  }, [data, lineIndex]);
  const replaceLineIndexSet = useMemo(() => new Set(replaceLineIndices), [replaceLineIndices]);
  const replaceTokenCount = useMemo(() => page.lines
    .filter((pageLine) => replaceLineIndexSet.has(pageLine.line_index))
    .reduce((count, pageLine) => count + pageLine.tokens.filter((token) => !token.deleted).length, 0),
  [page.lines, replaceLineIndexSet]);

  const reading = useMemo(() => {
    const included = [
      ...(replaceExistingBoxes ? [] : activeExistingBoxes.filter((b) => b.include)),
      ...proposals.filter((p) => p.selected),
    ].sort((a, b) => boxCenterX(a) - boxCenterX(b));
    return included.map((b) => b.label || "_").join("");
  }, [activeExistingBoxes, proposals, replaceExistingBoxes]);

  /* ─── Generate ─────────────────────────────────────────────── */

  const buildGeneratedProposals = () => {
    if (!data) return;
    return data.proposals.map((p) => toEditable(p, true));
  };

  const doGenerate = () => {
    const newProposals = buildGeneratedProposals();
    if (!newProposals) return;
    setProposals(newProposals);
    setGenerated(true);
    setFocusedId(null);
  };

  const handleReplaceExistingBoxesChange = (checked: boolean) => {
    setReplaceExistingBoxes(checked);
    setFocusedId(null);
  };

  /* ─── Proposal selection ───────────────────────────────────── */

  const toggleProposal = (id: string) => {
    setProposals((prev) => prev.map((p) => p.id === id ? { ...p, selected: !p.selected } : p));
  };

  const toggleFocusedBox = (id: string) => {
    setFocusedId((current) => current === id ? null : id);
  };

  const selectAllProposals = () => {
    const allSelected = proposals.every((p) => p.selected);
    setProposals((prev) => prev.map((p) => ({ ...p, selected: !allSelected })));
  };

  /* ─── Label editing ────────────────────────────────────────── */

  const setFocusedLabel = (label: string | null) => {
    if (!focusedId) return;
    const updateFn = (b: EditableBox) => b.id === focusedId ? { ...b, label } : b;
    setExistingBoxes((prev) => prev.map(updateFn));
    setProposals((prev) => prev.map(updateFn));
  };

  const deleteFocused = () => {
    if (!focusedId) return;
    if (isProposal(focusedId)) {
      setProposals((prev) => prev.filter((p) => p.id !== focusedId));
    } else {
      // Mark existing as deleted
      setDeletedExistingIds((prev) => new Set([...prev, focusedId]));
      setExistingBoxes((prev) => prev.filter((b) => b.id !== focusedId));
    }
    setFocusedId(null);
  };

  /* ─── Focus navigation ─────────────────────────────────────── */

  const focusNext = useCallback(() => {
    const sorted = [...allBoxes]
      .filter((b) => (b.include || b.selected) && !deletedExistingIds.has(b.id))
      .sort((a, b) => boxCenterX(a) - boxCenterX(b));
    const idx = sorted.findIndex((b) => b.id === focusedId);
    const next = sorted[(idx + 1) % sorted.length];
    if (next) setFocusedId(next.id);
  }, [allBoxes, focusedId, deletedExistingIds]);

  const focusPrev = useCallback(() => {
    const sorted = [...allBoxes]
      .filter((b) => (b.include || b.selected) && !deletedExistingIds.has(b.id))
      .sort((a, b) => boxCenterX(a) - boxCenterX(b));
    const idx = sorted.findIndex((b) => b.id === focusedId);
    const prev = sorted[(idx - 1 + sorted.length) % sorted.length];
    if (prev) setFocusedId(prev.id);
  }, [allBoxes, focusedId, deletedExistingIds]);

  /* ─── Draw & drag ──────────────────────────────────────────── */

  const handleCanvasMouseDown = (event: React.MouseEvent) => {
    if (!data || !drawMode) {
      setFocusedId(null);
      return;
    }
    const point = clientToImage(event.clientX, event.clientY);
    if (!point) return;
    event.preventDefault();
    // Ctrl+click = lacuna dot
    if (event.ctrlKey) {
      const half = LACUNA_DOT_BOX_SIZE / 2;
      const dot: EditableBox = {
        id: drawnBoxId(lineIndex ?? 0),
        x0: point.x - half, y0: point.y - half, x1: point.x + half, y1: point.y + half,
        label: ".", source: "drawn", source_component_ids: [], split_method: "manual_lacuna_dot",
        confidence: "usable", kind: "lacuna_dot", include: true, selected: true,
      };
      setProposals((prev) => [...prev, dot].sort((a, b) => a.x0 - b.x0));
      setFocusedId(dot.id);
      return;
    }
    setDrag({ kind: "draw", startX: point.x, startY: point.y, x: point.x, y: point.y });
  };

  const handleBoxMouseDown = (event: React.MouseEvent, box: EditableBox) => {
    if (drawMode) return;
    const point = clientToImage(event.clientX, event.clientY);
    if (!point) return;
    const normalized = normalizeBox(box);
    event.preventDefault();
    event.stopPropagation();
    setDrag({
      kind: "move", id: box.id,
      offsetX: point.x - normalized.x0, offsetY: point.y - normalized.y0,
      width: normalized.x1 - normalized.x0, height: normalized.y1 - normalized.y0,
    });
  };

  const handleResizeMouseDown = (event: React.MouseEvent, box: EditableBox, corner: "nw" | "ne" | "sw" | "se") => {
    const point = clientToImage(event.clientX, event.clientY);
    if (!point) return;
    event.preventDefault();
    event.stopPropagation();
    setFocusedId(box.id);
    setDrag({ kind: "resize", id: box.id, corner });
  };

  const updateBox = (id: string, updater: (b: EditableBox) => EditableBox) => {
    setExistingBoxes((prev) => prev.map((b) => b.id === id ? updater(b) : b));
    setProposals((prev) => prev.map((b) => b.id === id ? updater(b) : b));
  };

  const handleMouseMove = (event: React.MouseEvent) => {
    if (!drag) return;
    const point = clientToImage(event.clientX, event.clientY);
    if (!point) return;
    if (drag.kind === "draw") { setDrag({ ...drag, x: point.x, y: point.y }); return; }
    if (drag.kind === "move") {
      updateBox(drag.id, (b) => {
        const x0 = point.x - drag.offsetX;
        const y0 = point.y - drag.offsetY;
        return { ...b, x0, y0, x1: x0 + drag.width, y1: y0 + drag.height };
      });
      return;
    }
    updateBox(drag.id, (b) => {
      const next = { ...b };
      if (drag.corner.includes("n")) next.y0 = point.y;
      if (drag.corner.includes("s")) next.y1 = point.y;
      if (drag.corner.includes("w")) next.x0 = point.x;
      if (drag.corner.includes("e")) next.x1 = point.x;
      return next;
    });
  };

  const finishDrag = () => {
    if (!drag || lineIndex == null) return;
    if (drag.kind === "draw") {
      const draft = normalizeBox({
        id: drawnBoxId(lineIndex), x0: drag.startX, y0: drag.startY, x1: drag.x, y1: drag.y,
        label: null, source: "drawn" as const, source_component_ids: [], split_method: "manual_draw",
        confidence: "usable" as const, kind: "base" as const, include: true, selected: true,
      });
      if (boxWidth(draft) >= MIN_BOX_SIZE && boxHeight(draft) >= MIN_BOX_SIZE) {
        setProposals((prev) => [...prev, draft].sort((a, b) => a.x0 - b.x0));
        setFocusedId(draft.id);
      }
    } else {
      setExistingBoxes((prev) => prev.map(normalizeBox));
      setProposals((prev) => prev.map(normalizeBox));
    }
    setDrag(null);
  };

  /* ─── Accept (save) ────────────────────────────────────────── */

  const acceptChanges = () => {
    if (!data) return;
    const payload: EditMutationPayload = {};
    const shouldReplaceExistingBoxes = replaceExistingBoxes && generated;
    const replacementBlobDeletes = shouldReplaceExistingBoxes
      ? page.lines
        .filter((pageLine) => replaceLineIndexSet.has(pageLine.line_index))
        .flatMap((pageLine) => pageLine.tokens
          .filter((token) => !token.deleted)
          .map((token) => ({
            line_index: pageLine.line_index,
            blob_id: token.edit_id ?? token.blob_id,
            label: null,
            deleted: true,
            source: "manual" as const,
          })))
      : [];

    // Updates to existing boxes (label/position changes)
    const updates = shouldReplaceExistingBoxes
      ? []
      : existingBoxes
        .filter((b) => {
          if (deletedExistingIds.has(b.id)) return false;
          const orig = data.existing_bboxes.find((o) => o.id === b.id);
          return orig && (orig.label !== b.label || orig.x0 !== b.x0 || orig.y0 !== b.y0 || orig.x1 !== b.x1 || orig.y1 !== b.y1);
        })
        .map((b) => ({ id: b.id, label: b.label, x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1 }));

    // Deleted existing boxes
    const deletedIds = shouldReplaceExistingBoxes
      ? [...new Set(data.existing_bboxes.map((box) => box.id))]
      : [...deletedExistingIds];

    // New boxes from selected proposals
    const creates = selectedProposals.map((p) => ({
      line_index: data.line_index,
      x0: p.x0, y0: p.y0, x1: p.x1, y1: p.y1,
      coord_space: "image" as const,
      kind: p.kind,
      label: p.label,
    }));

    if (replacementBlobDeletes.length) payload.blob_edits = replacementBlobDeletes;
    if (updates.length) payload.update_new_bboxes = updates;
    if (deletedIds.length) payload.delete_new_bboxes = deletedIds;
    if (creates.length) payload.new_bboxes = creates;

    if (!payload.update_new_bboxes?.length && !payload.new_bboxes?.length && !payload.delete_new_bboxes?.length) {
      onClose();
      return;
    }
    mutateEdit(payload, { onSuccess: onClose });
  };

  /* ─── Keyboard shortcuts ───────────────────────────────────── */

  const handleDialogKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Tab") {
      e.preventDefault();
      e.shiftKey ? focusPrev() : focusNext();
    }
  };

  /* ─── Canvas box render ────────────────────────────────────── */

  const renderBox = (box: EditableBox) => {
    const normalized = normalizeBox(box);
    const focused = focusedId === box.id;
    const proposal = isProposal(box.id);
    const stroke = boxStroke(box, focused, proposal);
    const handleSize = Math.max(4, Math.min(7, Math.min(boxWidth(normalized), boxHeight(normalized)) / 3));
    const handles: ["nw" | "ne" | "sw" | "se", number, number][] = [
      ["nw", normalized.x0, normalized.y0], ["ne", normalized.x1, normalized.y0],
      ["sw", normalized.x0, normalized.y1], ["se", normalized.x1, normalized.y1],
    ];
    const opacity = proposal && !box.selected ? 0.3 : 1;
    return (
      <g key={box.id} opacity={opacity}>
        <rect
          x={normalized.x0} y={normalized.y0}
          width={boxWidth(normalized)} height={boxHeight(normalized)}
          fill={focused ? "color-mix(in oklch, var(--color-glass-accent), transparent 80%)" : "transparent"}
          stroke={stroke}
          strokeWidth={focused ? 2 : 1.2}
          strokeDasharray={proposal ? "3 2" : undefined}
          vectorEffect="non-scaling-stroke"
          style={{ cursor: drawMode ? "crosshair" : "move" }}
          onMouseDown={(ev) => handleBoxMouseDown(ev, box)}
          onClick={(ev) => { ev.stopPropagation(); toggleFocusedBox(box.id); }}
        />
        {box.label && (
          <text
            x={normalized.x0 + 1}
            y={Math.max(view?.y ?? 0, normalized.y0 - 2)}
            fontSize={8} fill={stroke}
            style={{ fontFamily: "var(--font-coptic)", pointerEvents: "none" }}
          >
            {displayLabel(box.label)}
          </text>
        )}
        {focused && handles.map(([corner, x, y]) => (
          <rect
            key={corner}
            x={x - handleSize / 2} y={y - handleSize / 2}
            width={handleSize} height={handleSize}
            fill="var(--color-glass-accent)" stroke="var(--color-glass-bg)"
            strokeWidth={0.8} vectorEffect="non-scaling-stroke"
            style={{ cursor: `${corner}-resize` }}
            onMouseDown={(ev) => handleResizeMouseDown(ev, box, corner)}
          />
        ))}
      </g>
    );
  };

  const dragRect = drag?.kind === "draw" ? normalizeBox({ x0: drag.startX, y0: drag.startY, x1: drag.x, y1: drag.y }) : null;

  /* ─── Render ───────────────────────────────────────────────── */

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1, pr: 1 }}>
        <TextFieldsIcon fontSize="small" />
        <Typography component="span" variant="h6" sx={{ whiteSpace: "nowrap" }}>
          Page {page.page} · Line {line?.display_index ?? line?.line_index ?? ""}
        </Typography>
        {reading && (
          <Chip
            size="small" variant="outlined"
            label={reading}
            sx={{ ml: 2, fontFamily: "var(--font-coptic)", maxWidth: 400, fontSize: 14 }}
          />
        )}
        <Box sx={{ flex: 1 }} />
        <Tooltip title="Close (Esc)">
          <IconButton aria-label="Close" size="small" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </DialogTitle>

      <DialogContent
        dividers
        onKeyDown={handleDialogKeyDown}
        tabIndex={-1}
        sx={{ display: "flex", flexDirection: "column", gap: 2, p: 2 }}
      >
        {/* ═══ Preview ═══ */}
        <Box sx={{ minWidth: 0 }}>
          {/* Toolbar */}
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1, flexWrap: "wrap", gap: 0.5 }}>
            <Tooltip title="Detect missing character boxes from geometry">
              <Button size="small" variant="outlined" startIcon={<RestartAltIcon />} onClick={doGenerate} disabled={!data}>
                Generate
              </Button>
            </Tooltip>
            <Tooltip title="Draw a box (Ctrl+click for lacuna dot)">
              <Button
                size="small"
                variant={drawMode ? "contained" : "outlined"}
                startIcon={<DrawIcon />}
                onClick={() => setDrawMode((v) => !v)}
              >
                Draw
              </Button>
            </Tooltip>
            <Box sx={{ flex: 1 }} />
            <Chip size="small" label={`${existingBoxes.length - deletedExistingIds.size} saved`} color="success" variant="outlined" />
            {generated && (
              <Chip
                size="small"
                label={`${selectedProposals.length}/${proposals.length} proposals`}
                color="info" variant="outlined"
              />
            )}
          </Stack>

          {/* Canvas area */}
          {error && <Alert severity="error">Failed to load line data.</Alert>}
          {(isFetching || !data || !view) ? (
            <Box sx={{ minHeight: 180, display: "grid", placeItems: "center" }}>
              <CircularProgress size={24} />
            </Box>
          ) : (
            <Box
              ref={frameRef}
              onMouseDown={handleCanvasMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={finishDrag}
              onMouseLeave={finishDrag}
              sx={{
                position: "relative", width: "100%", height: view.height * scale,
                minHeight: 100, border: "1px solid var(--color-glass-border)",
                borderRadius: 1, overflow: "hidden",
                backgroundColor: "var(--color-glass-surface)",
                cursor: drawMode ? "crosshair" : "default",
              }}
            >
              <svg
                width="100%" height="100%"
                viewBox={`${view.x} ${view.y} ${view.width} ${view.height}`}
                preserveAspectRatio="none"
                style={{ position: "absolute", inset: 0 }}
              >
                <image
                  href={data.image_url} x={0} y={0}
                  width={data.image_size[0]} height={data.image_size[1]}
                  preserveAspectRatio="none" style={{ pointerEvents: "none" }}
                />
                {existingBoxes.filter((b) => !deletedExistingIds.has(b.id)).map(renderBox)}
                {proposals.map(renderBox)}
                {dragRect && (
                  <rect
                    x={dragRect.x0} y={dragRect.y0}
                    width={boxWidth(dragRect)} height={boxHeight(dragRect)}
                    fill="color-mix(in oklch, var(--color-glass-accent), transparent 82%)"
                    stroke="var(--color-glass-accent)" strokeWidth={1.4}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
              </svg>
            </Box>
          )}
        </Box>

        {/* ═══ Controls Under Preview ═══ */}
        <Stack spacing={1.5} sx={{ minWidth: 0, width: "100%" }}>
          {/* ─── Focused Box Label Editor ─── */}
          {focusedBox && (
            <Stack
              spacing={1}
              sx={{
                p: 1,
                borderRadius: 1,
                border: "1px solid var(--color-glass-border)",
                backgroundColor: "var(--color-glass-surface)",
              }}
            >
              <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
                <Typography variant="subtitle2" sx={{ flex: 1, fontWeight: 600 }}>
                  {isProposal(focusedBox.id) ? "Edit Selected Box" : "Edit Saved Box"}
                </Typography>
                <Chip
                  size="small" variant="outlined"
                  label={focusedBox.kind === "lacuna_dot" ? "dot" : focusedBox.kind}
                />
                <Chip
                  size="small" variant="outlined"
                  label={focusedBox.split_method.replaceAll("_", " ").slice(0, 24)}
                  sx={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}
                />
                <Tooltip title="Delete this box">
                  <IconButton size="small" color="error" onClick={deleteFocused}>
                    <DeleteOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Stack>
              <CopticKeyboard
                mode="single"
                value={focusedBox.label}
                onChange={setFocusedLabel}
                hideDiacritics={false}
                onCommit={focusNext}
              />
            </Stack>
          )}

          {/* ─── Proposal Multiselect ─── */}
          {generated && (
            <Stack
              spacing={1}
              sx={{
                p: 1,
                borderRadius: 1,
                border: "1px solid var(--color-glass-border)",
                backgroundColor: "var(--color-glass-surface)",
              }}
            >
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", gap: 1 }}>
                <Typography variant="subtitle2" sx={{ flex: 1, fontWeight: 600 }}>
                  Found Boxes ({selectedProposals.length}/{proposals.length} selected)
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<SelectAllIcon />}
                  onClick={selectAllProposals}
                  disabled={proposals.length === 0}
                >
                  {proposals.every((p) => p.selected) ? "Deselect all" : "Select all"}
                </Button>
              </Stack>
              <Stack
                direction="row"
                spacing={0.75}
                sx={{ alignItems: "center", px: 0.25 }}
              >
                <Checkbox
                  size="small"
                  checked={replaceExistingBoxes}
                  aria-label="Overwrite existing line data"
                  onChange={(event) => handleReplaceExistingBoxesChange(event.target.checked)}
                  sx={{ p: 0.25 }}
                />
                <Typography variant="body2" color="text.primary">
                  Overwrite existing line data on Accept ({replaceTokenCount} token{replaceTokenCount === 1 ? "" : "s"}, {activeExistingBoxes.length} saved box{activeExistingBoxes.length === 1 ? "" : "es"})
                </Typography>
              </Stack>
              {proposals.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ fontStyle: "italic" }}>
                  No missing boxes detected — geometry fully covered.
                </Typography>
              ) : (
                <Stack spacing={0.5} sx={{ maxHeight: 240, overflowY: "auto", pr: 0.25 }}>
                  {[...proposals].sort((a, b) => a.x0 - b.x0).map((p) => (
                    <Stack
                      key={p.id}
                      direction="row"
                      spacing={0.75}
                      sx={{
                        alignItems: "center",
                        px: 0.75, py: 0.65, borderRadius: 1,
                        border: "1px solid",
                        borderColor: p.selected
                          ? "color-mix(in oklch, var(--color-glass-accent), transparent 35%)"
                          : "var(--color-glass-border)",
                        cursor: "pointer",
                        backgroundColor: p.selected
                          ? "color-mix(in oklch, var(--color-glass-accent), transparent 88%)"
                          : "color-mix(in oklch, var(--color-glass-bg), transparent 40%)",
                        outline: focusedId === p.id ? "2px solid var(--color-glass-accent)" : "none",
                        outlineOffset: -2,
                        "&:hover": { backgroundColor: "var(--color-glass-surface)" },
                        transition: "background-color 0.1s",
                      }}
                      onClick={() => toggleFocusedBox(p.id)}
                    >
                      <Checkbox
                        size="medium"
                        checked={p.selected}
                        aria-label={p.selected ? "Deselect proposal" : "Select proposal"}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => {
                          e.stopPropagation();
                          toggleProposal(p.id);
                        }}
                        sx={{ p: 0.25 }}
                      />
                      <Chip
                        size="small"
                        label={p.selected ? "Use" : "Skip"}
                        color={p.selected ? "info" : "default"}
                        variant={p.selected ? "filled" : "outlined"}
                        sx={{ width: 52 }}
                      />
                      <Typography
                        sx={{
                          fontFamily: "var(--font-coptic)", fontSize: 16,
                          minWidth: 24, textAlign: "center",
                          color: p.label ? "var(--color-glass-fg)" : "var(--color-glass-muted)",
                        }}
                      >
                        {displayLabel(p.label)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {p.kind === "lacuna_dot" ? "dot" : p.split_method.replaceAll("_", " ").slice(0, 20)}
                      </Typography>
                    </Stack>
                  ))}
                </Stack>
              )}
            </Stack>
          )}

          {!generated && (
            <Box
              sx={{
                p: 1,
                borderRadius: 1,
                border: "1px dashed var(--color-glass-border)",
              }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.25 }}>
                Found Boxes
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: "italic" }}>
                Click Generate to show the multiselect list.
              </Typography>
              <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", mt: 0.75 }}>
                <Checkbox
                  size="small"
                  checked={replaceExistingBoxes}
                  aria-label="Overwrite existing line data"
                  onChange={(event) => handleReplaceExistingBoxesChange(event.target.checked)}
                  sx={{ p: 0.25 }}
                />
                <Typography variant="body2" color="text.primary">
                  Overwrite existing line data on Accept ({replaceTokenCount} token{replaceTokenCount === 1 ? "" : "s"}, {activeExistingBoxes.length} saved box{activeExistingBoxes.length === 1 ? "" : "es"})
                </Typography>
              </Stack>
            </Box>
          )}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ gap: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ flex: 1, pl: 2 }}>
          Tab / Shift+Tab navigate · Ctrl+click for dots
        </Typography>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          startIcon={editPending ? <CircularProgress size={14} /> : <CheckIcon />}
          disabled={!data || editPending}
          onClick={acceptChanges}
        >
          Accept
        </Button>
      </DialogActions>
    </Dialog>
  );
}
