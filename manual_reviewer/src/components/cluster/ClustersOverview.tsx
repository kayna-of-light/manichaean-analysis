"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { MemberCrop } from "@/components/cluster/MemberCrop";
import LaunchIcon from "@mui/icons-material/Launch";

interface ClusterSummary {
  cluster_id: number;
  active_count: number;
  baseline_count: number;
  override_label: string | null;
  sample_member: {
    page: string;
    line_index: number;
    blob_id: number;
    image_url: string;
    image_size: [number, number] | null;
    aabb: [number, number, number, number] | null;
  } | null;
}

type SortMode = "id" | "active_desc" | "active_asc" | "label";
type FilterMode = "all" | "with_label" | "without_label" | "unassigned" | "non_empty";

const PAGE_SIZE = 60;
const UNASSIGNED_CLUSTER = -1;

export function ClustersOverview() {
  const query = useQuery<{ clusters: ClusterSummary[] }>({
    queryKey: ["clusters", "overview"],
    queryFn: async () => {
      const res = await fetch(`/api/clusters`);
      if (!res.ok) throw new Error("clusters fetch failed");
      return res.json();
    },
  });

  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortMode>("id");
  const [filter, setFilter] = useState<FilterMode>("non_empty");
  const [page, setPage] = useState(0);

  // Reset paging when filters change.
  useEffect(() => {
    setPage(0);
  }, [search, sort, filter]);

  const clusters = query.data?.clusters ?? [];

  const visible = useMemo(() => {
    let list = clusters;
    switch (filter) {
      case "with_label":
        list = list.filter((c) => !!c.override_label);
        break;
      case "without_label":
        list = list.filter((c) => !c.override_label && c.cluster_id !== UNASSIGNED_CLUSTER);
        break;
      case "unassigned":
        list = list.filter((c) => c.cluster_id === UNASSIGNED_CLUSTER);
        break;
      case "non_empty":
        list = list.filter((c) => c.active_count > 0);
        break;
      case "all":
      default:
        break;
    }
    if (search.trim()) {
      const s = search.trim().toLowerCase();
      list = list.filter((c) => {
        if (String(c.cluster_id).includes(s)) return true;
        const lbl = c.override_label ?? "";
        return lbl.toLowerCase().includes(s);
      });
    }
    const sorted = [...list];
    switch (sort) {
      case "active_desc":
        sorted.sort((a, b) => b.active_count - a.active_count);
        break;
      case "active_asc":
        sorted.sort((a, b) => a.active_count - b.active_count);
        break;
      case "label":
        sorted.sort((a, b) => (a.override_label ?? "").localeCompare(b.override_label ?? ""));
        break;
      case "id":
      default:
        sorted.sort((a, b) => a.cluster_id - b.cluster_id);
        break;
    }
    return sorted;
  }, [clusters, filter, search, sort]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const pageItems = visible.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <Stack spacing={2}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1}
        sx={{ alignItems: { xs: "stretch", sm: "center" } }}
      >
        <TextField
          size="small"
          label="Search id or label"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 220 }}
        />
        <Select
          size="small"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortMode)}
          sx={{ minWidth: 180 }}
        >
          <MenuItem value="id">Sort: by id</MenuItem>
          <MenuItem value="active_desc">Sort: most active first</MenuItem>
          <MenuItem value="active_asc">Sort: least active first</MenuItem>
          <MenuItem value="label">Sort: by label</MenuItem>
        </Select>
        <Select
          size="small"
          value={filter}
          onChange={(e) => setFilter(e.target.value as FilterMode)}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="non_empty">Filter: non-empty</MenuItem>
          <MenuItem value="all">Filter: all clusters</MenuItem>
          <MenuItem value="with_label">Filter: has label</MenuItem>
          <MenuItem value="without_label">Filter: missing label</MenuItem>
          <MenuItem value="unassigned">Filter: unassigned (−1)</MenuItem>
        </Select>
        <Box sx={{ flex: 1 }} />
        <Typography variant="caption" color="text.secondary">
          {visible.length} cluster{visible.length === 1 ? "" : "s"} · page {page + 1}/{totalPages}
        </Typography>
        <Button
          size="small"
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={page === 0}
        >
          Prev
        </Button>
        <Button
          size="small"
          onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
          disabled={page >= totalPages - 1}
        >
          Next
        </Button>
      </Stack>

      {query.isLoading && (
        <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
          <CircularProgress />
        </Box>
      )}
      {query.isError && (
        <Typography color="error">{(query.error as Error).message}</Typography>
      )}
      {!query.isLoading && pageItems.length === 0 && (
        <Typography color="text.secondary">No clusters match these filters.</Typography>
      )}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
          gap: 1.25,
        }}
      >
        {pageItems.map((c) => {
          const padded = String(c.cluster_id).padStart(3, "0");
          return (
            <Box
              key={c.cluster_id}
              className="glass"
              sx={{
                p: 1,
                borderRadius: 2,
                display: "flex",
                flexDirection: "column",
                gap: 0.5,
                position: "relative",
              }}
            >
              <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
                <Typography
                  sx={{
                    fontVariantNumeric: "tabular-nums",
                    fontWeight: 600,
                    fontSize: 14,
                  }}
                >
                  c{padded}
                  {c.cluster_id === UNASSIGNED_CLUSTER && " ✦"}
                </Typography>
                <Box sx={{ flex: 1 }} />
                <Chip
                  size="small"
                  label={`${c.active_count}`}
                  sx={{ height: 18, fontSize: 10 }}
                  color={c.active_count === 0 ? "default" : "primary"}
                  variant={c.active_count === 0 ? "outlined" : "filled"}
                />
                <Tooltip title={`Open cluster c${padded}`}>
                  <IconButton
                    size="small"
                    component={Link}
                    href={`/cluster/${c.cluster_id}`}
                    sx={{ p: 0.25 }}
                  >
                    <LaunchIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </Tooltip>
              </Stack>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: 64,
                  background: "var(--color-glass-surface)",
                  borderRadius: 1,
                }}
              >
                {c.sample_member ? (
                  <MemberCrop
                    imageUrl={c.sample_member.image_url}
                    imageSize={c.sample_member.image_size}
                    aabb={c.sample_member.aabb}
                    displayHeight={56}
                  />
                ) : (
                  <Typography variant="caption" color="text.disabled">
                    empty
                  </Typography>
                )}
              </Box>
              <Typography
                sx={{
                  fontFamily: "var(--font-coptic)",
                  fontSize: 20,
                  textAlign: "center",
                  lineHeight: 1.1,
                  minHeight: 24,
                  color: c.override_label ? "text.primary" : "text.disabled",
                }}
              >
                {c.override_label ?? "—"}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ textAlign: "center", fontSize: 10 }}
              >
                baseline {c.baseline_count}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Stack>
  );
}
