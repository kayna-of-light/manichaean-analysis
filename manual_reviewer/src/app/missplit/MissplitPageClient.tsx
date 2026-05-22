"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutlined";
import BuildIcon from "@mui/icons-material/BuildOutlined";
import UndoIcon from "@mui/icons-material/UndoOutlined";
import { MissplitEditor } from "@/components/missplit/MissplitEditor";

export interface MissplitItem {
  page: number;
  lineIndex: number;
  blobIds: number[];
  labels: string[];
  aabb: [number, number, number, number];
  blobAabbs: [number, number, number, number][];
  imgQuads: (number[][] | null)[];
  medianHeight: number;
  imageSize: [number, number];
  type: "oversplit" | "undersplit";
  status: "pending" | "correct" | "fixed";
  reviewId: number | null;
  newLabels: string[] | null;
  newBboxes: [number, number, number, number][] | null;
}

interface MissplitResponse {
  items: MissplitItem[];
  stats: { total: number; pending: number; correct: number; fixed: number };
}

const PAGE_SIZE = 100;

export function MissplitPageClient() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | "pending" | "correct" | "fixed">("pending");
  const [typeFilter, setTypeFilter] = useState<"all" | "oversplit" | "undersplit">("all");
  const [sort, setSort] = useState<"page" | "newest">("page");
  const [editorItem, setEditorItem] = useState<MissplitItem | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const { data, isLoading, isError, error } = useQuery<MissplitResponse>({
    queryKey: ["missplit"],
    queryFn: async () => {
      const res = await fetch("/api/missplit");
      if (!res.ok) throw new Error("Failed to load missplit data");
      return res.json();
    },
  });

  // Helper: optimistically patch a single item in the cache
  const patchItem = (
    target: MissplitItem,
    patch: Partial<MissplitItem>,
  ) => {
    qc.setQueryData<MissplitResponse>(["missplit"], (old) => {
      if (!old) return old;
      const key = `${target.page}:${target.lineIndex}:${target.blobIds.join(",")}`;
      const newItems = old.items.map((i) => {
        const k = `${i.page}:${i.lineIndex}:${i.blobIds.join(",")}`;
        return k === key ? { ...i, ...patch } : i;
      });
      // Recompute stats
      const stats = { total: newItems.length, pending: 0, correct: 0, fixed: 0 };
      for (const i of newItems) {
        if (i.status === "pending") stats.pending++;
        else if (i.status === "correct") stats.correct++;
        else if (i.status === "fixed") stats.fixed++;
      }
      return { items: newItems, stats };
    });
  };

  const markCorrect = useMutation({
    mutationFn: async (item: MissplitItem) => {
      const res = await fetch("/api/missplit/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "correct",
          page: item.page,
          lineIndex: item.lineIndex,
          blobIds: item.blobIds,
        }),
      });
      if (!res.ok) throw new Error("Failed to mark as correct");
      return res.json();
    },
    onMutate: (item) => {
      patchItem(item, { status: "correct", reviewId: -1 });
    },
  });

  const revertReview = useMutation({
    mutationFn: async (item: MissplitItem) => {
      const res = await fetch(`/api/missplit/resolve?reviewId=${item.reviewId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to revert");
      return res.json();
    },
    onMutate: (item) => {
      patchItem(item, { status: "pending", reviewId: null });
    },
  });

  if (isLoading) {
    return (
      <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }
  if (isError) {
    return (
      <Typography color="error" sx={{ p: 4 }}>
        {(error as Error).message}
      </Typography>
    );
  }

  const items = data?.items ?? [];
  const stats = data?.stats ?? { total: 0, pending: 0, correct: 0, fixed: 0 };
  const filtered = items.filter((i) => {
    if (filter !== "all" && i.status !== filter) return false;
    if (typeFilter !== "all" && i.type !== typeFilter) return false;
    return true;
  });

  // Sort
  const sorted = [...filtered];
  if (sort === "newest") {
    sorted.sort((a, b) => (b.reviewId ?? 0) - (a.reviewId ?? 0));
  }
  // "page" keeps the natural order (already sorted by page/line from the API)

  const visible = sorted.slice(0, visibleCount);
  const hasMore = visibleCount < sorted.length;

  // Group by page for display
  const byPage = new Map<number, MissplitItem[]>();
  for (const item of visible) {
    const list = byPage.get(item.page) ?? [];
    list.push(item);
    byPage.set(item.page, list);
  }

  return (
    <Box sx={{ p: 3, maxWidth: 1400, mx: "auto" }}>
      {/* Header */}
      <Stack direction="row" spacing={2} sx={{ alignItems: "center", mb: 3 }}>
        <Typography variant="h5" sx={{ flex: 1, fontWeight: 600 }}>
          Missplit Review
          {filtered.length > 0 && (
            <Typography component="span" variant="body2" sx={{ ml: 1, color: "var(--color-glass-muted)" }}>
              (showing {Math.min(visibleCount, filtered.length)} of {filtered.length})
            </Typography>
          )}
        </Typography>
        <Chip
          label={`${stats.total} total`}
          size="small"
          variant="outlined"
        />
        <Chip
          label={`${stats.pending} pending`}
          size="small"
          color="warning"
        />
        <Chip
          label={`${stats.correct} correct`}
          size="small"
          color="success"
        />
        <Chip
          label={`${stats.fixed} fixed`}
          size="small"
          color="info"
        />
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Filter</InputLabel>
          <Select
            value={filter}
            label="Filter"
            onChange={(e) => { const v = e.target.value as typeof filter; setFilter(v); setVisibleCount(PAGE_SIZE); if (v === "fixed" || v === "correct") setSort("newest"); else setSort("page"); }}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="pending">Pending</MenuItem>
            <MenuItem value="correct">Correct</MenuItem>
            <MenuItem value="fixed">Fixed</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 130 }}>
          <InputLabel>Type</InputLabel>
          <Select
            value={typeFilter}
            label="Type"
            onChange={(e) => { setTypeFilter(e.target.value as typeof typeFilter); setVisibleCount(PAGE_SIZE); }}
          >
            <MenuItem value="all">All types</MenuItem>
            <MenuItem value="oversplit">Oversplit</MenuItem>
            <MenuItem value="undersplit">Undersplit</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Sort</InputLabel>
          <Select
            value={sort}
            label="Sort"
            onChange={(e) => { setSort(e.target.value as typeof sort); setVisibleCount(PAGE_SIZE); }}
          >
            <MenuItem value="page">Page order</MenuItem>
            <MenuItem value="newest">Newest first</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      {/* Items grouped by page */}
      {[...byPage.entries()].map(([page, pageItems]) => (
        <Box key={page} sx={{ mb: 3 }}>
          <Typography
            variant="subtitle2"
            sx={{
              mb: 1,
              px: 1,
              py: 0.5,
              borderRadius: 1,
              backgroundColor: "var(--color-glass-surface)",
              display: "inline-block",
            }}
          >
            Page {String(page).padStart(3, "0")} — {pageItems.length} case{pageItems.length > 1 ? "s" : ""}
          </Typography>

          <Stack spacing={1}>
            {pageItems.map((item) => (
              <MissplitCard
                key={`${item.page}-${item.lineIndex}-${item.blobIds.join(",")}`}
                item={item}
                onMarkCorrect={() => markCorrect.mutate(item)}
                onEdit={() => setEditorItem(item)}
                onRevert={() => revertReview.mutate(item)}
                busy={markCorrect.isPending || revertReview.isPending}
              />
            ))}
          </Stack>
        </Box>
      ))}

      {hasMore && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 2, mb: 2 }}>
          <Button
            variant="outlined"
            onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
          >
            Load more ({filtered.length - visibleCount} remaining)
          </Button>
        </Box>
      )}

      {filtered.length === 0 && (
        <Typography sx={{ p: 4, textAlign: "center", color: "var(--color-glass-muted)" }}>
          No cases matching filter.
        </Typography>
      )}

      {/* Editor dialog */}
      {editorItem && (
        <MissplitEditor
          item={editorItem}
          open={Boolean(editorItem)}
          onClose={() => setEditorItem(null)}
          onSaved={() => {
            patchItem(editorItem, { status: "fixed", reviewId: editorItem.reviewId ?? -1 });
            setEditorItem(null);
          }}
        />
      )}
    </Box>
  );
}

/* --------------------------------------------------------------------------
 * Card for a single missplit group
 * -------------------------------------------------------------------------- */
function MissplitCard({
  item,
  onMarkCorrect,
  onEdit,
  onRevert,
  busy,
}: {
  item: MissplitItem;
  onMarkCorrect: () => void;
  onEdit: () => void;
  onRevert: () => void;
  busy: boolean;
}) {
  const page = String(item.page).padStart(3, "0");
  const imageUrl = `/api/image?root=textbody&p=${encodeURIComponent(`p${page}_text_body.jpg`)}`;

  // For fixed items with newBboxes, show repaired state; otherwise show original
  const showRepaired = item.status === "fixed" && item.newBboxes && item.newBboxes.length > 0;
  const previewBboxes = showRepaired ? item.newBboxes! : item.blobAabbs;

  // Compute crop from the relevant bboxes
  const previewAabb: [number, number, number, number] = showRepaired
    ? [
        Math.min(...item.newBboxes!.map((b) => b[0])),
        Math.min(...item.newBboxes!.map((b) => b[1])),
        Math.max(...item.newBboxes!.map((b) => b[2])),
        Math.max(...item.newBboxes!.map((b) => b[3])),
      ]
    : item.aabb;

  const [x0, y0, x1, y1] = previewAabb;
  const hasGeometry = x1 > x0 && y1 > y0;
  const pad = 4;
  const cropX = x0 - pad;
  const cropY = y0 - pad;
  const cropW = x1 - x0 + pad * 2;
  const cropH = y1 - y0 + pad * 2;
  const displayH = 48;
  const displayW = hasGeometry ? (cropW / cropH) * displayH : 48;

  return (
    <Box
      className="glass"
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        p: 1.5,
        borderRadius: 2,
        opacity: item.status !== "pending" ? 0.6 : 1,
      }}
    >
      {/* Thumbnail crop */}
      <Box
        sx={{
          width: displayW,
          height: displayH,
          minWidth: displayW,
          borderRadius: 1,
          overflow: "hidden",
          border: "1px solid var(--color-glass-border)",
          position: "relative",
          backgroundColor: "#1a1a1a",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {hasGeometry ? (
        <svg
          width={displayW}
          height={displayH}
          viewBox={`${cropX} ${cropY} ${cropW} ${cropH}`}
          style={{ display: "block" }}
        >
          <image
            href={imageUrl}
            x={0}
            y={0}
            width={item.imageSize[0]}
            height={item.imageSize[1]}
            preserveAspectRatio="none"
            style={{ pointerEvents: "none" }}
          />
          {previewBboxes.map((bbox, i) => (
            <rect
              key={i}
              x={bbox[0]}
              y={bbox[1]}
              width={bbox[2] - bbox[0]}
              height={bbox[3] - bbox[1]}
              fill="none"
              stroke={showRepaired
                ? "var(--color-glass-accent)"
                : item.type === "undersplit" ? "var(--color-review-unsplit)" : "var(--color-review-missplit)"}
              strokeWidth={0.8}
              strokeDasharray="2 1"
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
        ) : (
          <CheckCircleOutlineIcon sx={{ fontSize: 20, color: "success.main", opacity: 0.6 }} />
        )}
      </Box>

      {/* Info */}
      <Stack sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body2" sx={{ fontWeight: 500 }}>
          L{item.lineIndex} — {item.type === "undersplit"
            ? `1 blob (too wide)`
            : `${item.blobIds.length} fragments`}
          <Chip
            label={item.type === "undersplit" ? "undersplit" : "oversplit"}
            size="small"
            variant="outlined"
            sx={{
              ml: 1,
              height: 18,
              fontSize: "0.65rem",
              color: item.type === "undersplit"
                ? "var(--color-review-unsplit)"
                : "var(--color-review-missplit)",
              borderColor: item.type === "undersplit"
                ? "var(--color-review-unsplit)"
                : "var(--color-review-missplit)",
            }}
          />
        </Typography>
        <Typography
          variant="caption"
          sx={{ color: "var(--color-glass-muted)", fontFamily: "var(--font-coptic, serif)" }}
        >
          {item.labels.join(" · ")}
          {item.newLabels && (
            <span style={{ marginLeft: 8, color: "var(--color-glass-accent)" }}>
              → {item.newLabels.join("")}
            </span>
          )}
        </Typography>
      </Stack>

      {/* Status chip + revert */}
      {item.status !== "pending" && (
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Chip
            label={item.status}
            size="small"
            color={item.status === "correct" ? "success" : "info"}
            variant="outlined"
          />
          <Button
            size="small"
            variant="text"
            color="warning"
            startIcon={<UndoIcon />}
            onClick={onRevert}
            disabled={busy || !item.reviewId}
          >
            Revert
          </Button>
        </Stack>
      )}

      {/* Actions */}
      {item.status === "pending" && (
        <Stack direction="row" spacing={0.5}>
          <Button
            size="small"
            variant="outlined"
            color="success"
            startIcon={<CheckCircleOutlineIcon />}
            onClick={onMarkCorrect}
            disabled={busy}
          >
            Correct
          </Button>
          <Button
            size="small"
            variant="contained"
            startIcon={<BuildIcon />}
            onClick={onEdit}
          >
            Fix
          </Button>
        </Stack>
      )}
    </Box>
  );
}
