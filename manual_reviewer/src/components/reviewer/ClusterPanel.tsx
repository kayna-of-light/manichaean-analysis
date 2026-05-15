"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useState } from "react";

interface ClusterMember {
  page: string;
  line_index: number;
  blob_id: number;
  warped_bbox: [number, number, number, number];
  area: number;
  distance: number;
}

interface ClusterData {
  cluster_id: number;
  total: number;
  members: ClusterMember[];
  thumbs: string[];
  override: { label: string | null; note: string | null } | null;
}

interface Props {
  clusterId: number | null;
  onClose: () => void;
}

export function ClusterPanel({ clusterId, onClose }: Props) {
  const qc = useQueryClient();
  const [label, setLabel] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const query = useQuery<ClusterData>({
    queryKey: ["cluster", clusterId],
    queryFn: async () => {
      const res = await fetch(`/api/cluster/${clusterId}?limit=240`);
      if (!res.ok) throw new Error("cluster fetch failed");
      return res.json();
    },
    enabled: clusterId !== null,
  });

  const applyMutation = useMutation({
    mutationFn: async (action: "apply_label" | "clear" | "unset_blobs") => {
      let body: Record<string, unknown> = { action };
      if (action === "apply_label") body = { ...body, label };
      if (action === "unset_blobs") {
        body = {
          ...body,
          members: [...selected].map((k) => {
            const [page, lineIndex, blobId] = k.split("|");
            return { page, line_index: Number(lineIndex), blob_id: Number(blobId) };
          }),
        };
      }
      const res = await fetch(`/api/cluster/${clusterId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("apply failed");
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cluster", clusterId] });
      qc.invalidateQueries({ queryKey: ["page"] });
      setSelected(new Set());
    },
  });

  if (clusterId === null) return null;

  return (
    <Box
      className="glass"
      sx={{
        width: 360,
        flexShrink: 0,
        height: "100%",
        overflowY: "auto",
        p: 2,
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="h6">
          Cluster {String(clusterId).padStart(3, "0")}
        </Typography>
        <Box sx={{ flex: 1 }} />
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Stack>

      {query.isLoading && <CircularProgress size={20} sx={{ mt: 2 }} />}

      {query.data && (
        <>
          <Typography variant="caption" color="text.secondary">
            {query.data.total} members
            {query.data.override?.label
              ? ` · override: ${query.data.override.label}`
              : ""}
          </Typography>

          {query.data.thumbs.length > 0 && (
            <Box
              sx={{
                mt: 1,
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 0.5,
              }}
            >
              {query.data.thumbs.slice(0, 6).map((t) => (
                <Box
                  key={t}
                  component="img"
                  src={t}
                  alt="centroid"
                  sx={{
                    width: "100%",
                    height: 56,
                    objectFit: "contain",
                    bgcolor: "var(--color-glass-surface)",
                    borderRadius: 1,
                  }}
                />
              ))}
            </Box>
          )}

          <Divider sx={{ my: 1.5 }} />

          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              fullWidth
              label="Apply label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              slotProps={{
                htmlInput: {
                  style: { fontFamily: "var(--font-coptic)", fontSize: 20 },
                },
              }}
            />
            <Button
              variant="contained"
              size="small"
              onClick={() => applyMutation.mutate("apply_label")}
              disabled={applyMutation.isPending || label.length === 0}
            >
              Apply
            </Button>
          </Stack>
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => applyMutation.mutate("clear")}
            >
              Clear override
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="error"
              disabled={selected.size === 0}
              onClick={() => applyMutation.mutate("unset_blobs")}
            >
              Unset {selected.size}
            </Button>
          </Stack>

          <Divider sx={{ my: 1.5 }} />
          <Typography variant="overline" color="text.secondary">
            Members (closest first)
          </Typography>
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 0.5,
              mt: 1,
            }}
          >
            {query.data.members.map((m) => {
              const key = `${m.page}|${m.line_index}|${m.blob_id}`;
              const isSel = selected.has(key);
              return (
                <Box
                  key={key}
                  onClick={() =>
                    setSelected((s) => {
                      const ns = new Set(s);
                      if (ns.has(key)) ns.delete(key);
                      else ns.add(key);
                      return ns;
                    })
                  }
                  sx={{
                    p: 0.5,
                    borderRadius: 1,
                    border: isSel
                      ? "1.5px solid var(--color-glass-accent)"
                      : "1px solid var(--color-glass-border)",
                    cursor: "pointer",
                    textAlign: "center",
                  }}
                >
                  <Typography variant="caption" sx={{ fontSize: 10 }}>
                    p{m.page} · {m.line_index}/{m.blob_id}
                  </Typography>
                  <Box>
                    <Chip
                      label={m.distance.toFixed(2)}
                      size="small"
                      sx={{ height: 16, fontSize: 9 }}
                    />
                  </Box>
                </Box>
              );
            })}
          </Box>
        </>
      )}
    </Box>
  );
}
