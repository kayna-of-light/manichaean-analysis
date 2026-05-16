"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutlined";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import FlagOutlinedIcon from "@mui/icons-material/FlagOutlined";
import FlagIcon from "@mui/icons-material/Flag";
import AddBoxOutlinedIcon from "@mui/icons-material/AddBoxOutlined";
import DoneAllIcon from "@mui/icons-material/DoneAll";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import {
  usePageData,
  useEditMutation,
  usePagesList,
  type ReviewPage,
  type ReviewToken,
} from "@/components/reviewer/hooks";
import { LineSidebar } from "@/components/reviewer/LineSidebar";
import { LineCanvas } from "@/components/reviewer/LineCanvas";
import { TokenStrip } from "@/components/reviewer/TokenStrip";
import { CharChooser } from "@/components/reviewer/CharChooser";
import { ClusterPanel } from "@/components/reviewer/ClusterPanel";
import { useReviewerStore } from "@/components/reviewer/store";

type NewBbox = ReviewPage["new_bboxes"][number];

type OrderedLineItem =
  | { kind: "token"; x: number; token: ReviewToken }
  | { kind: "new"; x: number; nb: NewBbox };

function tokenCenterX(t: ReviewToken): number {
  const q = t.img_quad;
  if (q && q.length > 0) return q.reduce((sum, p) => sum + p[0], 0) / q.length;
  const bbox = t.geometry?.warped_bbox;
  if (bbox) return (bbox[0] + bbox[2]) / 2;
  return 0;
}

function newBboxCenterX(nb: NewBbox): number {
  return (nb.x0 + nb.x1) / 2;
}

function orderedLineItems(tokens: ReviewToken[], newBboxes: NewBbox[]): OrderedLineItem[] {
  return [
    ...tokens.filter((t) => !t.deleted).map((token) => ({ kind: "token" as const, x: tokenCenterX(token), token })),
    ...newBboxes.map((nb) => ({ kind: "new" as const, x: newBboxCenterX(nb), nb })),
  ].sort((a, b) => a.x - b.x);
}

function itemToNeighbor(item: OrderedLineItem | null) {
  if (!item) return null;
  if (item.kind === "new") {
    return {
      blobId: item.nb.id,
      label: item.nb.label,
      overlineMarkId: item.nb.overline_mark_id ?? null,
      isNewBbox: true,
    };
  }
  return {
    blobId: item.token.blob_id,
    label: item.token.effective_label,
    overlineMarkId: item.token.overline_mark_id ?? null,
  };
}

function toggledFlagStatus(status: string | undefined) {
  return status === "flagged" ? "pending" : "flagged";
}

function toggledDoneStatus(status: string | undefined) {
  return status === "done" ? "pending" : "done";
}

export default function ReviewPage() {
  const params = useParams<{ page: string }>();
  const router = useRouter();
  const pageId = (params?.page ?? "").padStart(3, "0");
  const { data, isLoading, error } = usePageData(pageId);
  const { data: pagesList } = usePagesList();
  const editMutation = useEditMutation(pageId);

  const selectedLine = useReviewerStore((s) => s.selectedLine);
  const setSelectedLine = useReviewerStore((s) => s.setSelectedLine);
  const openChooser = useReviewerStore((s) => s.openChooser);
  const closeChooser = useReviewerStore((s) => s.closeChooser);
  const chooserAnchor = useReviewerStore((s) => s.chooserAnchor);
  const selectedBlobId = useReviewerStore((s) => s.selectedBlobId);

  const [popoverEl, setPopoverEl] = useState<HTMLElement | null>(null);
  const [clusterId, setClusterId] = useState<number | null>(null);
  const [drawLineIndex, setDrawLineIndex] = useState<number | null>(null);
  const [pendingNewBboxOpen, setPendingNewBboxOpen] = useState<string | null>(null);
  const lineRefs = useRef(new Map<number, HTMLDivElement>());

  const setLineRef = useCallback((lineIndex: number, node: HTMLDivElement | null) => {
    if (node) lineRefs.current.set(lineIndex, node);
    else lineRefs.current.delete(lineIndex);
  }, []);

  const scrollToLine = useCallback((lineIndex: number, behavior: ScrollBehavior = "smooth") => {
    setSelectedLine(lineIndex);
    requestAnimationFrame(() => {
      lineRefs.current.get(lineIndex)?.scrollIntoView({ behavior, block: "start" });
    });
  }, [setSelectedLine]);

  // default-select the first line
  useEffect(() => {
    if (data && selectedLine === null && data.lines.length > 0) {
      setSelectedLine(data.lines[0].line_index);
    }
  }, [data, selectedLine, setSelectedLine]);

  // Auto-open chooser on newly created bbox after data refetch
  useEffect(() => {
    if (!pendingNewBboxOpen || !data) return;
    const nb = data.new_bboxes.find((b) => b.id === pendingNewBboxOpen);
    if (!nb) return;
    const lineEl = lineRefs.current.get(nb.line_index);
    if (!lineEl) return;
    setPendingNewBboxOpen(null);
    // Create virtual anchor at center of the line card
    const rect = lineEl.getBoundingClientRect();
    const line = data.lines.find((l) => l.line_index === nb.line_index);
    const lineNewBboxes = data.new_bboxes.filter((b) => b.line_index === nb.line_index);
    const items = orderedLineItems(line?.tokens ?? [], lineNewBboxes);
    const idx = items.findIndex((item) => item.kind === "new" && item.nb.id === nb.id);
    const left = idx > 0 ? itemToNeighbor(items[idx - 1]) : null;
    const right = idx >= 0 && idx < items.length - 1 ? itemToNeighbor(items[idx + 1]) : null;
    const virtual = {
      getBoundingClientRect: () =>
        ({
          x: rect.left + rect.width / 2,
          y: rect.bottom,
          left: rect.left + rect.width / 2,
          top: rect.bottom,
          right: rect.left + rect.width / 2,
          bottom: rect.bottom,
          width: 0,
          height: 0,
          toJSON: () => ({}),
        }) as DOMRect,
    } as unknown as HTMLElement;
    setPopoverEl(virtual);
    openChooser({
      page: pageId,
      pageInt: data.page_int,
      lineIndex: nb.line_index,
      blobId: nb.id,
      currentLabel: nb.label,
      currentDiacritics: nb.diacritics ?? [],
      candidates: [],
      hasOverline: nb.overline_mark_id != null,
      overlineMarkId: nb.overline_mark_id ?? null,
      leftNeighbor: left,
      rightNeighbor: right,
      isNewBbox: true,
      pendingOverline: { self: undefined, left: undefined, right: undefined },
    });
  }, [pendingNewBboxOpen, data, pageId, openChooser, setPopoverEl]);

  // keyboard: j/k step lines, f flag, d done
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (chooserAnchor) return; // chooser owns keys
      if (!data) return;
      const idxArr = data.lines.map((l) => l.line_index);
      const cur = selectedLine ?? idxArr[0];
      const pos = idxArr.indexOf(cur);
      if (e.key === "j" || e.key === "ArrowDown") {
        const next = idxArr[Math.min(pos + 1, idxArr.length - 1)];
        scrollToLine(next);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        const next = idxArr[Math.max(pos - 1, 0)];
        scrollToLine(next);
      } else if (e.key === "f") {
        const curLine = data.lines.find((l) => l.line_index === cur);
        editMutation.mutate({
          line_status: { line_index: cur, status: toggledFlagStatus(curLine?.status) },
        });
      } else if (e.key === "d") {
        const curLine = data.lines.find((l) => l.line_index === cur);
        editMutation.mutate({
          line_status: { line_index: cur, status: toggledDoneStatus(curLine?.status) },
        });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [data, selectedLine, scrollToLine, editMutation, chooserAnchor]);

  if (isLoading) {
    return (
      <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }
  if (error || !data) {
    return (
      <Box sx={{ p: 4 }}>
        <Typography color="error">page {pageId} not found</Typography>
      </Box>
    );
  }

  const pageIds = pagesList?.pages.map((p) => p.page) ?? [];
  const cpos = pageIds.indexOf(pageId);
  const prev = cpos > 0 ? pageIds[cpos - 1] : null;
  const next = cpos >= 0 && cpos < pageIds.length - 1 ? pageIds[cpos + 1] : null;

  const onTokenClick = (
    t: ReviewToken,
    evt: { clientX: number; clientY: number },
  ) => {
    // synthesize a virtual anchor at the click position so the popover lands here
    const virtual = {
      getBoundingClientRect: () =>
        ({
          x: evt.clientX,
          y: evt.clientY,
          left: evt.clientX,
          top: evt.clientY,
          right: evt.clientX,
          bottom: evt.clientY,
          width: 0,
          height: 0,
          toJSON: () => ({}),
        }) as DOMRect,
    } as unknown as HTMLElement;
    setPopoverEl(virtual);

    setSelectedLine(t.line_index);
    const line = data.lines.find((l) => l.line_index === t.line_index);
    const lineNewBboxes = data.new_bboxes.filter((nb) => nb.line_index === t.line_index);
    const items = orderedLineItems(line?.tokens ?? [], lineNewBboxes);
    const idx = items.findIndex(
      (item) => item.kind === "token" && item.token.blob_id === t.blob_id && item.token.line_index === t.line_index,
    );
    const left = idx > 0 ? itemToNeighbor(items[idx - 1]) : null;
    const right = idx >= 0 && idx < items.length - 1 ? itemToNeighbor(items[idx + 1]) : null;

    openChooser({
      page: pageId,
      pageInt: data.page_int,
      lineIndex: t.line_index,
      blobId: t.blob_id,
      currentLabel: t.effective_label,
      currentDiacritics: [],
      candidates: t.candidates,
      hasOverline: t.overline_mark_id != null,
      overlineMarkId: t.overline_mark_id ?? null,
      leftNeighbor: left,
      rightNeighbor: right,
      pendingOverline: { self: undefined, left: undefined, right: undefined },
    });
  };

  const openNewBboxChooser = (
    nb: NewBbox,
    evt: { clientX: number; clientY: number } | null,
  ) => {
    setSelectedLine(nb.line_index);
    const rect = lineRefs.current.get(nb.line_index)?.getBoundingClientRect();
    const x = evt?.clientX ?? (rect ? rect.left + rect.width / 2 : 0);
    const y = evt?.clientY ?? (rect ? rect.bottom : 0);
    const virtual = {
      getBoundingClientRect: () =>
        ({
          x,
          y,
          left: x,
          top: y,
          right: x,
          bottom: y,
          width: 0,
          height: 0,
          toJSON: () => ({}),
        }) as DOMRect,
    } as unknown as HTMLElement;
    setPopoverEl(virtual);

    const line = data.lines.find((l) => l.line_index === nb.line_index);
    const lineNewBboxes = data.new_bboxes.filter((b) => b.line_index === nb.line_index);
    const items = orderedLineItems(line?.tokens ?? [], lineNewBboxes);
    const idx = items.findIndex((item) => item.kind === "new" && item.nb.id === nb.id);
    const left = idx > 0 ? itemToNeighbor(items[idx - 1]) : null;
    const right = idx >= 0 && idx < items.length - 1 ? itemToNeighbor(items[idx + 1]) : null;

    openChooser({
      page: pageId,
      pageInt: data.page_int,
      lineIndex: nb.line_index,
      blobId: nb.id,
      currentLabel: nb.label,
      currentDiacritics: nb.diacritics ?? [],
      candidates: [],
      hasOverline: nb.overline_mark_id != null,
      overlineMarkId: nb.overline_mark_id ?? null,
      leftNeighbor: left,
      rightNeighbor: right,
      isNewBbox: true,
      pendingOverline: { self: undefined, left: undefined, right: undefined },
    });
  };

  return (
    <Box sx={{ display: "flex", height: "calc(100dvh - 114px)", gap: 1.5 }}>
      <LineSidebar
        lines={data.lines}
        selectedIndex={selectedLine}
        onSelect={scrollToLine}
      />

      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, minHeight: 0 }}>
        <Stack
          direction="row"
          spacing={1}
          sx={{ mb: 1.5, alignItems: "center" }}
        >
          <Typography variant="h6">Page {pageId}</Typography>
          <Chip
            size="small"
            label={`${data.lines.length} lines`}
            sx={{ height: 22 }}
          />
          <Box sx={{ flex: 1 }} />
          <IconButton
            size="small"
            disabled={!prev}
            onClick={() => prev && router.push(`/review/${prev}`)}
          >
            <ChevronLeftIcon />
          </IconButton>
          <IconButton
            size="small"
            disabled={!next}
            onClick={() => next && router.push(`/review/${next}`)}
          >
            <ChevronRightIcon />
          </IconButton>
        </Stack>

        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            pr: 1,
            pb: 2,
            display: "flex",
            flexDirection: "column",
            gap: 1.5,
          }}
        >
          {data.lines.map((line) => {
            const lineNewBboxes = data.new_bboxes.filter((nb) => nb.line_index === line.line_index);
            const mappedNewBboxes = lineNewBboxes.map((nb) => ({
              id: nb.id,
              x0: nb.x0,
              y0: nb.y0,
              x1: nb.x1,
              y1: nb.y1,
              label: nb.label,
              overline_mark_id: nb.overline_mark_id ?? null,
            }));
            const isSelectedLine = selectedLine === line.line_index;
            const isDrawing = drawLineIndex === line.line_index;
            return (
              <Box
                key={line.line_index}
                ref={(node: HTMLDivElement | null) => setLineRef(line.line_index, node)}
                className="glass line-card"
                onFocus={() => setSelectedLine(line.line_index)}
                onMouseEnter={() => setSelectedLine(line.line_index)}
                sx={{
                  position: "relative",
                  p: 1.5,
                  pt: 1,
                  flexShrink: 0,
                  overflow: "visible",
                  scrollMarginTop: 8,
                  border: isSelectedLine
                    ? "1px solid var(--color-glass-accent)"
                    : "1px solid transparent",
                  "& .line-toolbar": {
                    opacity: 0,
                    visibility: "hidden",
                    transition: "opacity 120ms ease",
                  },
                  "&:hover .line-toolbar, &:focus-within .line-toolbar": {
                    opacity: 1,
                    visibility: "visible",
                  },
                }}
              >
                {/* Ruler-style line number, top-right corner */}
                <Typography
                  component="span"
                  sx={{
                    position: "absolute",
                    top: 4,
                    right: 8,
                    fontSize: 10,
                    fontWeight: 600,
                    lineHeight: 1,
                    letterSpacing: 0.5,
                    fontVariantNumeric: "tabular-nums",
                    color: "text.disabled",
                    pointerEvents: "none",
                    userSelect: "none",
                    zIndex: 2,
                  }}
                >
                  {String(line.line_index).padStart(2, "0")}
                </Typography>

                {/* Status badge, top-left corner — only when done or flagged */}
                {(line.status === "done" || line.status === "flagged") && (
                  <Box
                    sx={{
                      position: "absolute",
                      top: 4,
                      left: 6,
                      display: "flex",
                      alignItems: "center",
                      gap: 0.5,
                      px: 0.5,
                      py: 0.25,
                      borderRadius: 0.75,
                      bgcolor: line.status === "done" ? "success.main" : "warning.main",
                      color: "common.white",
                      lineHeight: 1,
                      pointerEvents: "none",
                      zIndex: 2,
                      boxShadow: "0 1px 2px rgba(0,0,0,0.25)",
                    }}
                  >
                    {line.status === "done" ? (
                      <CheckCircleIcon sx={{ fontSize: 12 }} />
                    ) : (
                      <FlagIcon sx={{ fontSize: 12 }} />
                    )}
                  </Box>
                )}

                {/* Hover toolbar, top-right, floats above content */}
                <Stack
                  className="line-toolbar"
                  direction="row"
                  spacing={0.25}
                  sx={{
                    position: "absolute",
                    top: 4,
                    right: 32,
                    alignItems: "center",
                    px: 0.5,
                    py: 0.25,
                    borderRadius: 1,
                    bgcolor: "rgba(20,20,24,0.72)",
                    backdropFilter: "blur(6px)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    zIndex: 3,
                  }}
                >
                  <Tooltip title="Reset line">
                    <IconButton
                      size="small"
                      sx={{ p: 0.5 }}
                      onClick={() => {
                        if (!confirm(`Reset line ${line.line_index} to initial state? All edits on this line will be removed.`)) return;
                        editMutation.mutate({ reset_line: { line_index: line.line_index } });
                      }}
                    >
                      <RestartAltIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={isDrawing ? "Cancel drawing" : "Add bbox"}>
                    <IconButton
                      size="small"
                      sx={{ p: 0.5, color: isDrawing ? "primary.main" : "inherit" }}
                      onClick={() => setDrawLineIndex(isDrawing ? null : line.line_index)}
                    >
                      <AddBoxOutlinedIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={line.status === "flagged" ? "Unflag (f)" : "Flag (f)"}>
                    <IconButton
                      size="small"
                      sx={{ p: 0.5, color: line.status === "flagged" ? "warning.main" : "inherit" }}
                      onClick={() =>
                        editMutation.mutate({
                          line_status: {
                            line_index: line.line_index,
                            status: toggledFlagStatus(line.status),
                          },
                        })
                      }
                    >
                      <FlagOutlinedIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={line.status === "done" ? "Reopen (d)" : "Done (d)"}>
                    <IconButton
                      size="small"
                      sx={{ p: 0.5, color: line.status === "done" ? "success.main" : "inherit" }}
                      onClick={() =>
                        editMutation.mutate({
                          line_status: {
                            line_index: line.line_index,
                            status: toggledDoneStatus(line.status),
                          },
                        })
                      }
                    >
                      <CheckCircleOutlineIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                </Stack>

                <LineCanvas
                  page={data}
                  line={line}
                  highlightBlob={isSelectedLine ? selectedBlobId : null}
                  onTokenClick={onTokenClick}
                  drawMode={isDrawing}
                  newBboxes={mappedNewBboxes}
                  onNewBbox={(bbox) => {
                    editMutation.mutate(
                      {
                        new_bboxes: [
                          {
                            line_index: line.line_index,
                            ...bbox,
                            coord_space: "image",
                          },
                        ],
                      },
                      {
                        onSuccess: (result) => {
                          const newId = result?.new_bboxes?.[0];
                          if (newId) setPendingNewBboxOpen(newId);
                        },
                      },
                    );
                    setDrawLineIndex(null);
                  }}
                  onNewBboxClick={(nb, evt) => {
                    const source = data.new_bboxes.find((b) => b.id === nb.id);
                    if (source) openNewBboxChooser(source, evt);
                  }}
                />
                <TokenStrip
                  line={line}
                  onTokenClick={onTokenClick}
                  newBboxes={mappedNewBboxes}
                  onNewBboxClick={(nb, evt) => {
                    const source = data.new_bboxes.find((b) => b.id === nb.id);
                    if (source) openNewBboxChooser(source, evt);
                  }}
                />
              </Box>
            );
          })}

          {(prev || next) && (
            <Stack
              direction="row"
              spacing={2}
              sx={{
                mt: 1,
                pt: 2,
                pb: 1,
                alignItems: "center",
                justifyContent: "space-between",
                borderTop: "1px solid var(--color-glass-border, rgba(255,255,255,0.08))",
              }}
            >
              <Button
                size="small"
                variant="outlined"
                startIcon={<ChevronLeftIcon />}
                disabled={!prev}
                onClick={() => prev && router.push(`/review/${prev}`)}
                sx={{ visibility: prev ? "visible" : "hidden" }}
              >
                Page {prev}
              </Button>
              {(() => {
                const pendingLines = data.lines.filter(
                  (l) => l.status !== "done" && l.status !== "flagged",
                );
                if (pendingLines.length === 0) {
                  return (
                    <Typography variant="caption" color="text.secondary">
                      End of page {pageId}
                    </Typography>
                  );
                }
                return (
                  <Button
                    size="small"
                    variant="outlined"
                    color="success"
                    startIcon={<DoneAllIcon />}
                    disabled={editMutation.isPending}
                    onClick={async () => {
                      if (
                        !confirm(
                          `Mark all ${pendingLines.length} unflagged pending line(s) on page ${pageId} as done?`,
                        )
                      )
                        return;
                      for (const l of pendingLines) {
                        await editMutation.mutateAsync({
                          line_status: { line_index: l.line_index, status: "done" },
                        });
                      }
                    }}
                  >
                    Mark {pendingLines.length} as done
                  </Button>
                );
              })()}
              <Button
                size="small"
                variant="outlined"
                endIcon={<ChevronRightIcon />}
                disabled={!next}
                onClick={() => next && router.push(`/review/${next}`)}
                sx={{ visibility: next ? "visible" : "hidden" }}
              >
                Page {next}
              </Button>
            </Stack>
          )}
        </Box>
      </Box>

      <ClusterPanel clusterId={clusterId} onClose={() => setClusterId(null)} />

      <CharChooser
        pageId={pageId}
        anchorEl={popoverEl}
        onClose={() => {
          setPopoverEl(null);
          closeChooser();
        }}
      />
    </Box>
  );
}
