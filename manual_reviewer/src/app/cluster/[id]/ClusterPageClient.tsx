"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutlined";
import { MemberCrop } from "@/components/cluster/MemberCrop";
import { ClusterLabelDialog } from "@/components/cluster/ClusterLabelDialog";
import { NewClusterDialog } from "@/components/cluster/NewClusterDialog";

interface ClusterMember {
  page: string;
  line_index: number;
  source_line_index: number | null;
  blob_id: number;
  origin_cluster: number;
  reassigned: boolean;
  unset: boolean;
  deleted?: boolean;
  label: string | null;
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
  active_total: number;
  original_total: number;
  reassigned_in: number;
  reassigned_away: number;
  unset_excluded: number;
  offset: number;
  limit: number;
  members: ClusterMember[];
  thumbs: string[];
  override: { label: string | null; note: string | null } | null;
}

type FilterMode = "all" | "reassigned" | "original";
type ApiMember = {
  page: string;
  line_index: number;
  blob_id: number;
  from_cluster?: number | null;
};
type ApiAction =
  | "apply_label"
  | "clear"
  | "unset_blobs"
  | "reassign_blobs"
  | "clear_reassignments";

const UNASSIGNED_CLUSTER = -1;

function memberKey(m: { page: string; line_index: number; blob_id: number }) {
  return `${m.page}|${m.line_index}|${m.blob_id}`;
}

export function ClusterPageClient({ clusterId }: { clusterId: number }) {
  const qc = useQueryClient();
  const router = useRouter();
  const [target, setTarget] = useState<string>("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [anchorKey, setAnchorKey] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [labelDialogOpen, setLabelDialogOpen] = useState(false);
  const [newClusterDialogOpen, setNewClusterDialogOpen] = useState(false);
  const gridRef = useRef<HTMLDivElement>(null);

  const query = useQuery<ClusterData>({
    queryKey: ["cluster-page", clusterId],
    queryFn: async () => {
      const res = await fetch(`/api/cluster/${clusterId}?limit=5000`);
      if (!res.ok) throw new Error("cluster fetch failed");
      return res.json();
    },
  });

  const mutation = useMutation({
    mutationFn: async (input: {
      action: ApiAction;
      members?: ApiMember[];
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
      setAnchorKey(null);
    },
  });

  const members = query.data?.members ?? [];
  const filtered = useMemo(() => {
    if (filter === "all") return members;
    if (filter === "reassigned") return members.filter((m) => m.reassigned);
    return members.filter((m) => !m.reassigned);
  }, [members, filter]);

  const filteredKeys = useMemo(() => filtered.map(memberKey), [filtered]);
  const filteredKeyIndex = useMemo(() => {
    const m = new Map<string, number>();
    filteredKeys.forEach((k, i) => m.set(k, i));
    return m;
  }, [filteredKeys]);

  const selectedMembers: ApiMember[] = useMemo(() => {
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

  const selectedReassignedMembers: ApiMember[] = useMemo(
    () =>
      selectedMembers.filter((m) => {
        const orig = filtered.find(
          (f) =>
            f.page === m.page &&
            f.line_index === m.line_index &&
            f.blob_id === m.blob_id,
        );
        return Boolean(orig?.reassigned);
      }),
    [filtered, selectedMembers],
  );

  const allFilteredSelected =
    filteredKeys.length > 0 && filteredKeys.every((k) => selected.has(k));

  const apply = (input: Parameters<typeof mutation.mutate>[0]) => {
    mutation.mutate(input);
  };

  // --- Selection handlers ---------------------------------------------------
  const onMemberClick = useCallback(
    (key: string, e: React.MouseEvent) => {
      const isShift = e.shiftKey;
      const isMod = e.ctrlKey || e.metaKey;
      setSelected((prev) => {
        const next = new Set(prev);
        if (isShift && anchorKey && filteredKeyIndex.has(anchorKey)) {
          const a = filteredKeyIndex.get(anchorKey)!;
          const b = filteredKeyIndex.get(key);
          if (b == null) return next;
          const [lo, hi] = a <= b ? [a, b] : [b, a];
          for (let i = lo; i <= hi; i++) next.add(filteredKeys[i]);
          // anchor unchanged on shift
          return next;
        }
        if (isMod) {
          if (next.has(key)) next.delete(key);
          else next.add(key);
          setAnchorKey(key);
          return next;
        }
        // plain click: replace selection
        const replaced = new Set<string>([key]);
        setAnchorKey(key);
        return replaced;
      });
    },
    [anchorKey, filteredKeyIndex, filteredKeys],
  );

  const clearSelection = useCallback(() => {
    setSelected(new Set());
    setAnchorKey(null);
  }, []);

  const selectAllFiltered = useCallback(() => {
    setSelected(new Set(filteredKeys));
    if (filteredKeys.length > 0) setAnchorKey(filteredKeys[0]);
  }, [filteredKeys]);

  // Keyboard: Ctrl/Cmd+A, Esc
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      const inField =
        tag === "input" || tag === "textarea" || target?.isContentEditable;
      if (inField) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        e.preventDefault();
        selectAllFiltered();
      } else if (e.key === "Escape") {
        if (selected.size > 0) {
          e.preventDefault();
          clearSelection();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectAllFiltered, clearSelection, selected.size]);

  // --- Cluster label actions ------------------------------------------------
  const onSubmitLabel = (lbl: string) => {
    apply({ action: "apply_label", label: lbl });
    setLabelDialogOpen(false);
  };
  const onClearOverride = () => apply({ action: "clear" });

  // --- Selection actions ----------------------------------------------------
  const onMoveSelection = () => {
    const to = parseInt(target, 10);
    if (!Number.isFinite(to) || to === clusterId) return;
    if (selectedMembers.length === 0) return;
    apply({ action: "reassign_blobs", members: selectedMembers, to_cluster: to });
  };

  const onClearFromCluster = () => {
    if (selectedMembers.length === 0) return;
    // Reassign to the global unassigned sentinel. This both removes them from
    // this cluster and ensures any label inherited from this cluster's
    // override stops applying (unassigned cluster has no override). Per-blob
    // manual edits and diacritics are untouched.
    apply({
      action: "reassign_blobs",
      members: selectedMembers,
      to_cluster: UNASSIGNED_CLUSTER,
    });
  };

  const onUndoReassign = () => {
    if (selectedReassignedMembers.length === 0) return;
    apply({ action: "clear_reassignments", members: selectedReassignedMembers });
  };

  const onUnsetSelection = () => {
    if (selectedMembers.length === 0) return;
    apply({ action: "unset_blobs", members: selectedMembers });
  };

  const cidPadded = String(clusterId).padStart(3, "0");
  const data = query.data;
  const hasSelection = selectedMembers.length > 0;
  const targetParsed = parseInt(target, 10);
  const targetValid =
    Number.isFinite(targetParsed) && targetParsed !== clusterId;

  return (
    <Box sx={{ p: 2, display: "flex", flexDirection: "column", gap: 2 }}>
      <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
        <IconButton component={Link} href="/" size="small" aria-label="back">
          <ArrowBackIcon fontSize="small" />
        </IconButton>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Cluster {cidPadded}
          {clusterId === UNASSIGNED_CLUSTER && " (unassigned)"}
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
            {data.active_total} active · baseline {data.original_total} · +in{" "}
            {data.reassigned_in} · −out {data.reassigned_away} · unset{" "}
            {data.unset_excluded}
          </Typography>
        )}
      </Stack>

      <Box className="glass" sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="overline" color="text.secondary">
          Cluster label
        </Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 1, alignItems: "center" }}>
          <Box
            sx={{
              minWidth: 120,
              px: 1.5,
              py: 0.75,
              borderRadius: 1,
              border: "1px solid var(--color-glass-border)",
              background: "var(--color-glass-surface)",
              fontFamily: "var(--font-coptic)",
              fontSize: 22,
              textAlign: "center",
              color: data?.override?.label
                ? "text.primary"
                : "text.disabled",
            }}
          >
            {data?.override?.label ?? "—"}
          </Box>
          <Button
            variant="contained"
            size="small"
            onClick={() => setLabelDialogOpen(true)}
            disabled={mutation.isPending}
          >
            {data?.override?.label ? "Edit cluster label…" : "Set cluster label…"}
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={onClearOverride}
            disabled={mutation.isPending || !data?.override?.label}
          >
            Remove cluster label
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

        {/* Selection toolbar */}
        <Stack
          direction="row"
          spacing={1}
          sx={{
            mt: 1,
            alignItems: "center",
            flexWrap: "wrap",
            rowGap: 1,
          }}
        >
          <Chip
            size="small"
            color={hasSelection ? "primary" : "default"}
            label={`${selectedMembers.length} selected of ${filteredKeys.length}`}
          />
          <Button
            size="small"
            variant="outlined"
            onClick={selectAllFiltered}
            disabled={filteredKeys.length === 0 || allFilteredSelected}
          >
            Select all
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={clearSelection}
            disabled={!hasSelection}
          >
            Clear selection
          </Button>

          <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

          <Tooltip
            title={
              hasSelection
                ? "Reassign selected blobs to another existing cluster"
                : "Select blobs first"
            }
          >
            <span>
              <TextField
                size="small"
                label="Target cluster #"
                value={target}
                onChange={(e) => setTarget(e.target.value.replace(/[^0-9-]/g, ""))}
                sx={{ width: 140 }}
                disabled={!hasSelection}
              />
            </span>
          </Tooltip>
          <Tooltip
            title={
              !hasSelection
                ? "Select blobs first"
                : !targetValid
                  ? "Enter a different cluster number"
                  : `Move ${selectedMembers.length} blob(s) to cluster ${target}`
            }
          >
            <span>
              <Button
                size="small"
                variant="contained"
                onClick={onMoveSelection}
                disabled={
                  mutation.isPending ||
                  !hasSelection ||
                  !targetValid
                }
              >
                Move selection to cluster
              </Button>
            </span>
          </Tooltip>

          <Tooltip
            title={
              hasSelection
                ? "Remove selected blobs from this cluster. They move to the global Unassigned cluster; any label inherited from this cluster's override is dropped. Per-blob manual edits stay intact."
                : "Select blobs first"
            }
          >
            <span>
              <Button
                size="small"
                variant="outlined"
                color="warning"
                onClick={onClearFromCluster}
                disabled={mutation.isPending || !hasSelection}
              >
                Clear from this cluster
              </Button>
            </span>
          </Tooltip>

          <Tooltip
            title={
              hasSelection
                ? "Move selected blobs into a brand-new cluster (you can label it next)"
                : "Select blobs first"
            }
          >
            <span>
              <Button
                size="small"
                variant="outlined"
                color="primary"
                startIcon={<AddCircleOutlineIcon fontSize="small" />}
                onClick={() => setNewClusterDialogOpen(true)}
                disabled={mutation.isPending || !hasSelection}
              >
                Create new cluster from selection…
              </Button>
            </span>
          </Tooltip>

          <Tooltip
            title={
              selectedReassignedMembers.length > 0
                ? `Restore ${selectedReassignedMembers.length} reassigned blob(s) to their original cluster`
                : "Select reassigned blobs first"
            }
          >
            <span>
              <Button
                size="small"
                variant="outlined"
                onClick={onUndoReassign}
                disabled={
                  mutation.isPending || selectedReassignedMembers.length === 0
                }
                startIcon={<RestoreIcon fontSize="small" />}
              >
                Undo reassignment ({selectedReassignedMembers.length})
              </Button>
            </span>
          </Tooltip>

          <Tooltip
            title={
              hasSelection
                ? "Mark selected blobs as not-a-character. They are removed from the page reviewer and from this cluster."
                : "Select blobs first"
            }
          >
            <span>
              <Button
                size="small"
                variant="outlined"
                color="error"
                onClick={onUnsetSelection}
                disabled={mutation.isPending || !hasSelection}
              >
                Mark as not-a-character
              </Button>
            </span>
          </Tooltip>
        </Stack>

        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mt: 0.75, display: "block" }}
        >
          Click to select. Ctrl/Cmd-click to toggle. Shift-click to extend range
          from the last anchor. Ctrl/Cmd-A selects all. Esc clears.
        </Typography>

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
          ref={gridRef}
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(108px, 1fr))",
            gap: 1,
            userSelect: "none",
          }}
        >
          {filtered.map((m) => {
            const key = memberKey(m);
            const isSel = selected.has(key);
            const isAnchor = key === anchorKey;
            return (
              <Box
                key={key}
                onClick={(e) => onMemberClick(key, e)}
                sx={{
                  p: 0.75,
                  borderRadius: 1,
                  border: isSel
                    ? "2px solid var(--color-glass-accent, #C8A465)"
                    : m.deleted
                      ? "1.5px solid rgba(244, 67, 54, 0.6)"
                      : m.reassigned
                        ? "1.5px dashed var(--color-secondary, #b08)"
                        : "1px solid var(--color-glass-border)",
                  outline: isAnchor
                    ? "1px dotted var(--color-glass-accent, #C8A465)"
                    : "none",
                  outlineOffset: isAnchor ? 2 : 0,
                  background: isSel
                    ? "rgba(200, 164, 101, 0.15)"
                    : m.deleted
                      ? "rgba(244, 67, 54, 0.08)"
                      : "var(--color-glass-surface)",
                  opacity: m.deleted ? 0.55 : 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: 0.5,
                  alignItems: "stretch",
                  cursor: "pointer",
                  transition: "background 120ms ease-out",
                }}
              >
                {m.deleted && (
                  <Chip
                    label="DELETED"
                    size="small"
                    sx={{
                      alignSelf: "center",
                      height: 16,
                      fontSize: 9,
                      fontWeight: 700,
                      bgcolor: "rgba(244, 67, 54, 0.2)",
                      color: "#f44336",
                      borderRadius: 0.5,
                    }}
                  />
                )}
                <Box sx={{ display: "flex", justifyContent: "center" }}>
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
                  sx={{
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <Tooltip title={`Open p${m.page} line ${m.line_index}`}>
                    <IconButton
                      size="small"
                      component={Link}
                      href={`/review/${m.page}`}
                      target="_blank"
                      onClick={(e) => e.stopPropagation()}
                      sx={{ p: 0.25 }}
                    >
                      <LaunchIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                  <Typography
                    variant="caption"
                    sx={{
                      fontSize: 10,
                      color: "text.secondary",
                      textAlign: "right",
                    }}
                  >
                    p{m.page}·{m.line_index}/{m.blob_id}
                  </Typography>
                </Stack>
                {m.label && (
                  <Typography
                    sx={{
                      fontFamily: "var(--font-coptic)",
                      fontSize: 18,
                      lineHeight: 1,
                      textAlign: "center",
                      color: "text.primary",
                    }}
                  >
                    {m.label}
                  </Typography>
                )}
                {(m.reassigned || m.unset || m.distance != null) && (
                  <Stack
                    direction="row"
                    spacing={0.25}
                    sx={{ flexWrap: "wrap" }}
                  >
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

      <ClusterLabelDialog
        open={labelDialogOpen}
        clusterId={clusterId}
        initialLabel={data?.override?.label ?? null}
        memberCount={data?.active_total ?? 0}
        busy={mutation.isPending}
        onClose={() => setLabelDialogOpen(false)}
        onSubmit={onSubmitLabel}
      />
      <NewClusterDialog
        open={newClusterDialogOpen}
        memberCount={selectedMembers.length}
        busy={mutation.isPending}
        onClose={() => setNewClusterDialogOpen(false)}
        onSubmit={async (lbl) => {
          try {
            const res = await fetch(`/api/clusters`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                action: "create_from_selection",
                label: lbl,
                members: selectedMembers,
              }),
            });
            if (!res.ok) throw new Error(await res.text());
            const json = (await res.json()) as { new_cluster_id: number };
            qc.invalidateQueries({ queryKey: ["cluster-page", clusterId] });
            qc.invalidateQueries({ queryKey: ["clusters"] });
            qc.invalidateQueries({ queryKey: ["page"] });
            setNewClusterDialogOpen(false);
            setSelected(new Set());
            setAnchorKey(null);
            router.push(`/cluster/${json.new_cluster_id}`);
          } catch (err) {
            console.error("create_from_selection failed", err);
            setNewClusterDialogOpen(false);
          }
        }}
      />
    </Box>
  );
}
