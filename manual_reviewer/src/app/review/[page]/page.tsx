"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutlined";
import FlagOutlinedIcon from "@mui/icons-material/FlagOutlined";
import AddBoxOutlinedIcon from "@mui/icons-material/AddBoxOutlined";
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
  const [drawMode, setDrawMode] = useState(false);
  const [pendingNewBboxOpen, setPendingNewBboxOpen] = useState<string | null>(null);
  const stripContainer = useRef<HTMLDivElement>(null);

  // default-select the first line
  useEffect(() => {
    if (data && selectedLine === null && data.lines.length > 0) {
      setSelectedLine(data.lines[0].line_index);
    }
  }, [data, selectedLine, setSelectedLine]);

  // Auto-open chooser on newly created bbox after data refetch
  useEffect(() => {
    if (!pendingNewBboxOpen || !data || !stripContainer.current) return;
    const nb = data.new_bboxes.find((b) => b.id === pendingNewBboxOpen);
    if (!nb) return;
    setPendingNewBboxOpen(null);
    // Create virtual anchor at center of the strip container
    const rect = stripContainer.current.getBoundingClientRect();
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
        setSelectedLine(next);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        const next = idxArr[Math.max(pos - 1, 0)];
        setSelectedLine(next);
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
  }, [data, selectedLine, setSelectedLine, editMutation, chooserAnchor]);

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

  const currentLine = data.lines.find((l) => l.line_index === selectedLine) ?? data.lines[0];
  const currentNewBboxes = data.new_bboxes.filter(
    (nb) => nb.line_index === currentLine?.line_index,
  );

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

    const lineTokens = currentLine?.tokens ?? [];
    const items = orderedLineItems(lineTokens, currentNewBboxes);
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
    const rect = stripContainer.current?.getBoundingClientRect();
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
    <Box sx={{ display: "flex", height: "calc(100vh - 64px)", gap: 1.5 }}>
      <LineSidebar
        lines={data.lines}
        selectedIndex={selectedLine}
        onSelect={setSelectedLine}
      />

      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
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
          ref={stripContainer}
          className="glass"
          sx={{ p: 1.5, mb: 0, overflow: "hidden" }}
        >
          {currentLine && (
            <>
              <LineCanvas
                page={data}
                line={currentLine}
                highlightBlob={selectedBlobId}
                onTokenClick={onTokenClick}
                drawMode={drawMode}
                newBboxes={data.new_bboxes
                  .filter((nb) => nb.line_index === currentLine.line_index)
                  .map((nb) => ({ id: nb.id, x0: nb.x0, y0: nb.y0, x1: nb.x1, y1: nb.y1, label: nb.label, overline_mark_id: nb.overline_mark_id ?? null }))}
                onNewBbox={(bbox) => {
                  if (!currentLine) return;
                  editMutation.mutate(
                    {
                      new_bboxes: [
                        {
                          line_index: currentLine.line_index,
                          ...bbox,
                          coord_space: "image",
                        },
                      ],
                    },
                    {
                      onSuccess: (result) => {
                        // Auto-open chooser on the newly created bbox
                        const newId = result?.new_bboxes?.[0];
                        if (newId) setPendingNewBboxOpen(newId);
                      },
                    },
                  );
                  setDrawMode(false);
                }}
                onNewBboxClick={(nb, evt) => {
                  const source = data.new_bboxes.find((b) => b.id === nb.id);
                  if (source) openNewBboxChooser(source, evt);
                }}
              />
              <TokenStrip
                line={currentLine}
                onTokenClick={onTokenClick}
                newBboxes={data.new_bboxes
                  .filter((nb) => nb.line_index === currentLine.line_index)
                  .map((nb) => ({ id: nb.id, x0: nb.x0, y0: nb.y0, x1: nb.x1, y1: nb.y1, label: nb.label, overline_mark_id: nb.overline_mark_id ?? null }))}
                onNewBboxClick={(nb, evt) => {
                  const source = data.new_bboxes.find((b) => b.id === nb.id);
                  if (source) openNewBboxChooser(source, evt);
                }}
              />
            </>
          )}
        </Box>

        <Stack
          direction="row"
          spacing={1}
          sx={{ py: 0.5, alignItems: "center" }}
        >
          <Typography variant="overline" color="text.secondary">
            Line {currentLine?.line_index} · {currentLine?.status}
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button
            size="small"
            startIcon={<RestartAltIcon />}
            color="warning"
            onClick={() => {
              if (!currentLine) return;
              if (!confirm(`Reset line ${currentLine.line_index} to initial state? All edits on this line will be removed.`)) return;
              editMutation.mutate({ reset_line: { line_index: currentLine.line_index } });
            }}
          >
            Reset line
          </Button>
          <Button
            size="small"
            startIcon={<AddBoxOutlinedIcon />}
            variant={drawMode ? "contained" : "text"}
            color={drawMode ? "primary" : "inherit"}
            onClick={() => setDrawMode((m) => !m)}
          >
            {drawMode ? "Drawing…" : "Add bbox"}
          </Button>
          <Button
            size="small"
            variant={currentLine?.status === "flagged" ? "contained" : "text"}
            color={currentLine?.status === "flagged" ? "warning" : "inherit"}
            startIcon={<FlagOutlinedIcon />}
            onClick={() =>
              currentLine &&
              editMutation.mutate({
                line_status: {
                  line_index: currentLine.line_index,
                  status: toggledFlagStatus(currentLine.status),
                },
              })
            }
          >
            Flag (f)
          </Button>
          <Button
            size="small"
            variant={currentLine?.status === "done" ? "contained" : "text"}
            color={currentLine?.status === "done" ? "success" : "inherit"}
            startIcon={<CheckCircleOutlineIcon />}
            onClick={() =>
              currentLine &&
              editMutation.mutate({
                line_status: {
                  line_index: currentLine.line_index,
                  status: toggledDoneStatus(currentLine.status),
                },
              })
            }
          >
            Done (d)
          </Button>
        </Stack>
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
