"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import LaunchIcon from "@mui/icons-material/Launch";
import RestoreIcon from "@mui/icons-material/Restore";
import { MemberCrop } from "@/components/cluster/MemberCrop";

interface ClusterMember {
  page: string;
  line_index: number;
  blob_id: number;
  origin_cluster: number;
  reassigned: boolean;
  unset: boolean;
  warped_bbox: [number, number, number, number];
  area: number;
  distance: number | null;
  img_quad: [number, number][] | null;
  aabb: [number, number, number, number] | null;
  image_url: string;
  image_size: [number, number] | null;
}

interface ClusterData {
  cluster_id: number;
  total: number;
  original_total: number;
  reassigned_in: number;
  reassigned_away: number;
  offset: number;
  limit: number;
  members: ClusterMember[];
  thumbs: string[];
  override: { label: string | null; note: string | null } | null;
}

function memberKey(m: { page: string; line_index: number; blob_id: number }) {
  return `${m.page}|${m.line_index}|${m.blob_id}`;
}

export function ClusterPageClient({ clusterId }: { clusterId: number }) {
  const qc = useQueryClient();
  const [label, setLabel] = useState("");
  const [target, setTarget] = useState<string>("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<"all" | "reassigned" | "original">("all");

  const query = useQuery<ClusterData>({
    queryKey: ["cluster-page", clusterId],
    queryFn: async () => {
      const res = await fetch(`/api/cluster/${clusterId}?limit=2000`);
      if (!res.ok) throw new Error("cluster fetch failed");
      return res.json();
    },
  });

  const mutation = useMutation({
    mutationFn: async (input: {
      action:
        | "apply_label"
        | "clear"
        | "unset_blobs"
        | "reassign_blobs"
        | "clear_reassignments";
      members?: Array<{
        page: string;
        line_index: number;
        blob_id: number;
        from_cluster?: number | null;
      }>;
      to_cluster?: number;
      label?: string;
    }) => {
      const res = await fetch(`/api/cluster/${clusterId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`apply failed: ${res.status} ${txt}`);
      }
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cluster-page", clusterId] });
      qc.invalidateQueries({ queryKey: ["page"] });
      setSelected(new Set());
    },
  });

  const members = query.data?.members ?? [];
  const filtered = useMemo(() => {
    if (filter === "all") return members;
    if (filter === "reassigned") return members.filter((m) => m.reassigned);
    return members.filter((m) => !m.reassigned);
  }, [members, filter]);

  const selectedMembers = useMemo(() => {
    if (selected.size === 0) return [];
    return filtered
      .filter((m) => selected.has(memberKey(m)))
      .map((m) => ({
        page: m.page,
        line_index: m.line_index,
        blob_id: m.blob_id,
        from_cluster: m.origin_cluster,
      }));
  }, [filtered, selected]);

  const allFilteredKeys = useMemo(
    () => filtered.map(memberKey),
    [filtered],
  );
  const allSelected = allFilteredKeys.length > 0 &&
    allFilteredKeys.every((k) => selected.has(k));

  const toggleAll = () => {
    setSelected((s) => {
      const ns = new Set(s);
      if (allSelected) {
        for (const k of allFilteredKeys) ns.delete(k);
      } else {
        for (const k of allFilteredKeys) ns.add(k);
      }
      return ns;
    });
  };

  const apply = (input: Parameters<typeof mutation.mutate>[0]) => {
    mutation.mutate(input);
  };

  const onApplyLabel = () => {
    if (!label) return;
    apply({ action: "apply_label", label });
  };

  const onClearOverride = () => apply({ action: "clear" });

  const onUnsetSelected = () => {
    if (selectedMembers.length === 0) return;
    apply({ action: "unset_blobs", members: selectedMembers });
  };

  const onReassignSelected = () => {
    const to = parseInt(target, 10);
    if (!Number.isFinite(to) || to === clusterId) return;
    if (selectedMembers.length === 0) return;
    apply({ action: "reassign_blobs", members: selectedMembers, to_cluster: to });
  };

  const onClearReassign = () => {
    const items = selectedMembers.filter((m) => {
      const orig = filtered.find(
        (f) => f.page === m.page && f.line_index === m.line_index && f.blob_id === m.blob_id,
      );
      return Boolean(orig?.reassigned);
    });
    if (items.length === 0) return;
    apply({ action: "clear_reassignments", members: items });
  };

  const cidPadded = String(clusterId).padStart(3, "0");
  const data = query.data;

  return (
    <Box sx={{ p: 2, display: "flex", flexDirection: "column", gap: 2 }}>
      <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
        <IconButton component={Link} href="/" size="small" aria-label="back">
          <ArrowBackIcon fontSize="small" />
        </IconButton>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Cluster {cidPadded}
        </Typography>
        {data?.override?.label ? (
          <Chip
            size="small"
            color="primary"
            label={`override: ${data.override.label}`}
          />
        ) : (
          <Chip size="small" variant="outlined" label="no override" />
        )}
        <Box sx={{ flex: 1 }} />
        {data && (
          <Typography variant="caption" color="text.secondary">
            {data.total} members · original {data.original_total} · +in{" "}
            {data.reassigned_in} · −out {data.reassigned_away}
          </Typography>
        )}
      </Stack>

      <Box className="glass" sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="overline" color="text.secondary">
          Cluster label
        </Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 1, alignItems: "center" }}>
          <TextField
            size="small"
            label="Apply label to whole cluster"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={data?.override?.label ?? ""}
            slotProps={{
              htmlInput: {
                style: { fontFamily: "var(--font-coptic)", fontSize: 20 },
              },
            }}
            sx={{ minWidth: 280 }}
          />
          <Button
            variant="contained"
            size="small"
            onClick={onApplyLabel}
            disabled={mutation.isPending || label.length === 0}
          >
            Apply
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={onClearOverride}
            disabled={mutation.isPending || !data?.override?.label}
          >
            Clear override
          </Button>
          <Box sx={{ flex: 1 }} />
          <Typography variant="caption" color="text.secondary">
            Cluster overrides apply to every member except blobs that already
            have a manual edit.
          </Typography>
        </Stack>
      </Box>

      <Box className="glass" sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography variant="overline" color="text.secondary">
            Members
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Stack direction="row" spacing={0.5}>
            {(["all", "original", "reassigned"] as const).map((f) => (
              <Button
                key={f}
                size="small"
                variant={filter === f ? "contained" : "outlined"}
                onClick={() => setFilter(f)}
                sx={{ textTransform: "none", py: 0.25 }}
              >
                {f}
              </Button>
            ))}
          </Stack>
        </Stack>

        <Stack
          direction="row"
          spacing={1}
          sx={{ mt: 1, alignItems: "center", flexWrap: "wrap" }}
        >
          <Button size="small" variant="outlined" onClick={toggleAll}>
            {allSelected ? "Clear selection" : "Select all (filtered)"}
          </Button>
          <Chip
            size="small"
            label={`${selected.size} selected`}
            color={selected.size > 0 ? "primary" : "default"}
          />
          <Box sx={{ flex: 1 }} />
          <TextField
            size="small"
            label="Reassign to cluster #"
            value={target}
            onChange={(e) => setTarget(e.target.value.replace(/[^0-9]/g, ""))}
            sx={{ width: 160 }}
          />
          <Button
            size="small"
            variant="contained"
            onClick={onReassignSelected}
            disabled={
              mutation.isPending ||
              selectedMembers.length === 0 ||
              !target ||
              parseInt(target, 10) === clusterId
            }
          >
            Move {selectedMembers.length} →
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="warning"
            onClick={onClearReassign}
            disabled={mutation.isPending || selectedMembers.length === 0}
            startIcon={<RestoreIcon fontSize="small" />}
          >
            Undo reassign
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="error"
            onClick={onUnsetSelected}
            disabled={mutation.isPending || selectedMembers.length === 0}
          >
            Unset {selectedMembers.length}
          </Button>
        </Stack>

        <Divider sx={{ my: 1.5 }} />

        {query.isLoading && (
          <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
            <CircularProgress />
          </Box>
        )}
        {query.isError && (
          <Typography color="error">
            {(query.error as Error).message}
          </Typography>
        )}
        {data && filtered.length === 0 && (
          <Typography color="text.secondary">No members.</Typography>
        )}

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(108px, 1fr))",
            gap: 1,
          }}
        >
          {filtered.map((m) => {
            const key = memberKey(m);
            const isSel = selected.has(key);
            const outline = isSel
              ? "2px solid var(--color-glass-accent)"
              : m.reassigned
                ? "1.5px dashed var(--color-secondary, #b08)"
                : "1px solid var(--color-glass-border)";
            return (
              <Box
                key={key}
                sx={{
                  p: 0.75,
                  borderRadius: 1,
                  border: outline,
                  background: "var(--color-glass-surface)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 0.5,
                  alignItems: "stretch",
                }}
              >
                <Box
                  onClick={() =>
                    setSelected((s) => {
                      const ns = new Set(s);
                      if (ns.has(key)) ns.delete(key);
                      else ns.add(key);
                      return ns;
                    })
                  }
                  sx={{
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "center",
                  }}
                >
                  <MemberCrop
                    imageUrl={m.image_url}
                    imageSize={m.image_size}
                    aabb={m.aabb}
                    displayHeight={64}
                  />
                </Box>
                <Stack
                  direction="row"
                  spacing={0.5}
                  sx={{ alignItems: "center", justifyContent: "space-between" }}
                >
                  <Tooltip title={`Open p${m.page} line ${m.line_index}`}>
                    <IconButton
                      size="small"
                      component={Link}
                      href={`/review/${m.page}`}
                      target="_blank"
                      sx={{ p: 0.25 }}
                    >
                      <LaunchIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                  <Typography
                    variant="caption"
                    sx={{ fontSize: 10, color: "text.secondary" }}
                  >
                    p{m.page}·{m.line_index}/{m.blob_id}
                  </Typography>
                </Stack>
                {(m.reassigned || m.unset || m.distance != null) && (
                  <Stack direction="row" spacing={0.25} sx={{ flexWrap: "wrap" }}>
                    {m.reassigned && (
                      <Chip
                        size="small"
                        color="secondary"
                        label={`from ${String(m.origin_cluster).padStart(3, "0")}`}
                        sx={{ height: 16, fontSize: 9 }}
                      />
                    )}
                    {m.unset && (
                      <Chip
                        size="small"
                        color="error"
                        label="unset"
                        sx={{ height: 16, fontSize: 9 }}
                      />
                    )}
                    {m.distance != null && (
                      <Chip
                        size="small"
                        variant="outlined"
                        label={m.distance.toFixed(2)}
                        sx={{ height: 16, fontSize: 9 }}
                      />
                    )}
                  </Stack>
                )}
              </Box>
            );
          })}
        </Box>
      </Box>

      {data && data.thumbs.length > 0 && (
        <Box className="glass" sx={{ p: 2, borderRadius: 2 }}>
          <Typography variant="overline" color="text.secondary">
            Centroid samples
          </Typography>
          <Box
            sx={{
              mt: 1,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(80px, 1fr))",
              gap: 0.5,
            }}
          >
            {data.thumbs.map((t) => (
              <Box
                key={t}
                component="img"
                src={t}
                alt="centroid"
                sx={{
                  width: "100%",
                  height: 80,
                  objectFit: "contain",
                  bgcolor: "var(--color-glass-surface)",
                  borderRadius: 1,
                }}
              />
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}
