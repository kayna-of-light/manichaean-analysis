"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  FormControlLabel,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutlined";
import DeleteIcon from "@mui/icons-material/Delete";
import LaunchIcon from "@mui/icons-material/Launch";
import SaveIcon from "@mui/icons-material/Save";
import { MemberCrop } from "@/components/cluster/MemberCrop";

interface EditorialMatchPreview {
  page: string;
  line_index: number;
  v1_line_index: number | null;
  token_count: number;
  token_keys: string[];
  blob_ids: number[];
  image_url: string;
  image_size: [number, number] | null;
  aabb: [number, number, number, number] | null;
}

interface EditorialArrayView {
  id: number;
  sentence_id: number;
  name: string | null;
  clusters: string;
  active: number;
  cluster_array: number[];
  length: number;
  char_count_no_spaces: number;
  length_matches_sentence: boolean;
  match_count: number;
  matches: EditorialMatchPreview[];
}

interface EditorialSentenceView {
  id: number;
  text: string;
  active: number;
  note: string | null;
  chars_no_spaces: string[];
  char_count_no_spaces: number;
  arrays: EditorialArrayView[];
}

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

type EditorialAction =
  | { action: "create_sentence"; text: string; active?: boolean; note?: string | null }
  | { action: "update_sentence"; id: number; text?: string; active?: boolean; note?: string | null }
  | { action: "delete_sentence"; id: number }
  | { action: "create_array"; sentence_id: number; name?: string | null; clusters: number[]; active?: boolean }
  | { action: "update_array"; id: number; name?: string | null; clusters?: number[]; active?: boolean }
  | { action: "delete_array"; id: number };

function clusterLabel(id: number): string {
  return id < 0 ? String(id) : String(id).padStart(3, "0");
}

function clusterSearchText(cluster: ClusterSummary): string {
  return `${cluster.cluster_id} ${clusterLabel(cluster.cluster_id)} ${cluster.override_label ?? ""}`.toLowerCase();
}

export function EditorialOverview() {
  const qc = useQueryClient();
  const [newSentence, setNewSentence] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const editorialQuery = useQuery<{ sentences: EditorialSentenceView[] }>({
    queryKey: ["editorial"],
    queryFn: async () => {
      const res = await fetch("/api/editorial");
      if (!res.ok) throw new Error("editorial fetch failed");
      return res.json();
    },
  });

  const clustersQuery = useQuery<{ clusters: ClusterSummary[] }>({
    queryKey: ["clusters", "overview"],
    queryFn: async () => {
      const res = await fetch("/api/clusters");
      if (!res.ok) throw new Error("clusters fetch failed");
      return res.json();
    },
  });

  const mutation = useMutation({
    mutationFn: async (action: EditorialAction) => {
      const res = await fetch("/api/editorial", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(action),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["editorial"] });
      qc.invalidateQueries({ queryKey: ["page"] });
    },
  });

  const sentences = editorialQuery.data?.sentences ?? [];
  const clusters = clustersQuery.data?.clusters ?? [];

  useEffect(() => {
    if (selectedId != null && sentences.some((item) => item.id === selectedId)) return;
    setSelectedId(sentences[0]?.id ?? null);
  }, [selectedId, sentences]);

  const selected = sentences.find((item) => item.id === selectedId) ?? null;

  const onAddSentence = () => {
    const text = newSentence.trim();
    if (!text) return;
    mutation.mutate({ action: "create_sentence", text, active: true }, {
      onSuccess: () => setNewSentence(""),
    });
  };

  if (editorialQuery.isLoading) {
    return (
      <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (editorialQuery.isError) {
    return <Typography color="error">{(editorialQuery.error as Error).message}</Typography>;
  }

  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", lg: "320px minmax(0, 1fr)" },
        gap: 2,
      }}
    >
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={1}>
          <TextField
            size="small"
            label="New sentence"
            value={newSentence}
            onChange={(event) => setNewSentence(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") onAddSentence();
            }}
            fullWidth
          />
          <Tooltip title="Add sentence">
            <span>
              <IconButton color="primary" onClick={onAddSentence} disabled={!newSentence.trim()}>
                <AddCircleOutlineIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>

        <Typography variant="caption" color="text.secondary">
          {sentences.length} sentence{sentences.length === 1 ? "" : "s"}
        </Typography>

        <Stack spacing={1} sx={{ maxHeight: 780, overflow: "auto", pr: 0.5 }}>
          {sentences.map((sentence) => (
            <Box
              key={sentence.id}
              onClick={() => setSelectedId(sentence.id)}
              className="glass"
              sx={{
                p: 1.25,
                borderRadius: 2,
                cursor: "pointer",
                outline: selectedId === sentence.id ? "2px solid var(--color-glass-accent)" : undefined,
              }}
            >
              <Stack direction="row" spacing={0.75} sx={{ alignItems: "center" }}>
                <Typography sx={{ fontWeight: 650, flex: 1 }}>{sentence.text}</Typography>
                <Chip size="small" label={sentence.active ? "on" : "off"} color={sentence.active ? "primary" : "default"} />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                {sentence.char_count_no_spaces} chars · {sentence.arrays.length} array{sentence.arrays.length === 1 ? "" : "s"}
              </Typography>
            </Box>
          ))}
        </Stack>
      </Stack>

      {selected ? (
        <SentenceEditor
          sentence={selected}
          clusters={clusters}
          mutationPending={mutation.isPending}
          mutate={(action) => mutation.mutate(action)}
        />
      ) : (
        <Box className="glass" sx={{ p: 3, borderRadius: 2 }}>
          <Typography color="text.secondary">No editorial sentence selected.</Typography>
        </Box>
      )}
    </Box>
  );
}

function SentenceEditor({
  sentence,
  clusters,
  mutationPending,
  mutate,
}: {
  sentence: EditorialSentenceView;
  clusters: ClusterSummary[];
  mutationPending: boolean;
  mutate: (action: EditorialAction) => void;
}) {
  const [text, setText] = useState(sentence.text);
  const [note, setNote] = useState(sentence.note ?? "");
  const [active, setActive] = useState(Boolean(sentence.active));

  useEffect(() => {
    setText(sentence.text);
    setNote(sentence.note ?? "");
    setActive(Boolean(sentence.active));
  }, [sentence.id, sentence.text, sentence.note, sentence.active]);

  const saveSentence = () => {
    mutate({
      action: "update_sentence",
      id: sentence.id,
      text: text.trim(),
      active,
      note: note.trim() || null,
    });
  };

  const deleteSentence = () => {
    if (!window.confirm(`Delete "${sentence.text}" and all its arrays?`)) return;
    mutate({ action: "delete_sentence", id: sentence.id });
  };

  const addArray = () => {
    mutate({
      action: "create_array",
      sentence_id: sentence.id,
      name: `array ${sentence.arrays.length + 1}`,
      clusters: [],
      active: true,
    });
  };

  return (
    <Stack spacing={2}>
      <Box className="glass" sx={{ p: 2, borderRadius: 2 }}>
        <Stack spacing={1.25}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1} sx={{ alignItems: { md: "center" } }}>
            <TextField
              label="Sentence"
              size="small"
              value={text}
              onChange={(event) => setText(event.target.value)}
              fullWidth
            />
            <FormControlLabel
              control={<Checkbox checked={active} onChange={(event) => setActive(event.target.checked)} />}
              label="Active"
              sx={{ whiteSpace: "nowrap" }}
            />
            <Button startIcon={<SaveIcon />} variant="contained" onClick={saveSentence} disabled={!text.trim() || mutationPending}>
              Save
            </Button>
            <Tooltip title="Delete sentence">
              <IconButton color="error" onClick={deleteSentence} disabled={mutationPending}>
                <DeleteIcon />
              </IconButton>
            </Tooltip>
          </Stack>
          <TextField
            label="Note"
            size="small"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            fullWidth
          />
          <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1 }}>
            <Chip label={`${sentence.char_count_no_spaces} chars without spaces`} />
            <Chip label={sentence.chars_no_spaces.join(" ") || "no characters"} variant="outlined" />
          </Stack>
        </Stack>
      </Box>

      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="h6" sx={{ flex: 1 }}>Cluster Arrays</Typography>
        <Button startIcon={<AddCircleOutlineIcon />} onClick={addArray} disabled={mutationPending}>
          Add Array
        </Button>
      </Stack>

      {sentence.arrays.length === 0 ? (
        <Box className="glass" sx={{ p: 2, borderRadius: 2 }}>
          <Typography color="text.secondary">No cluster arrays yet.</Typography>
        </Box>
      ) : (
        <Stack spacing={2}>
          {sentence.arrays.map((array) => (
            <ClusterArrayEditor
              key={array.id}
              sentence={sentence}
              array={array}
              clusters={clusters}
              mutationPending={mutationPending}
              mutate={mutate}
            />
          ))}
        </Stack>
      )}
    </Stack>
  );
}

function ClusterArrayEditor({
  sentence,
  array,
  clusters,
  mutationPending,
  mutate,
}: {
  sentence: EditorialSentenceView;
  array: EditorialArrayView;
  clusters: ClusterSummary[];
  mutationPending: boolean;
  mutate: (action: EditorialAction) => void;
}) {
  const [name, setName] = useState(array.name ?? "");
  const [active, setActive] = useState(Boolean(array.active));
  const [draftClusters, setDraftClusters] = useState<(number | null)[]>(array.cluster_array);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [clusterSearch, setClusterSearch] = useState("");

  useEffect(() => {
    setName(array.name ?? "");
    setActive(Boolean(array.active));
    setDraftClusters(array.cluster_array);
    setFocusedIndex(0);
  }, [array.id, array.name, array.active, array.cluster_array]);

  const allPositionsSet = draftClusters.every((item): item is number => Number.isInteger(item));
  const lengthMatches = draftClusters.length === sentence.char_count_no_spaces;
  const canSave = allPositionsSet && draftClusters.length > 0;

  const visibleClusters = useMemo(() => {
    const search = clusterSearch.trim().toLowerCase();
    const list = clusters.filter((cluster) => cluster.active_count > 0 || cluster.cluster_id < 0);
    const filtered = search
      ? list.filter((cluster) => clusterSearchText(cluster).includes(search))
      : list;
    return filtered.slice(0, 120);
  }, [clusters, clusterSearch]);

  const setLength = (length: number) => {
    const nextLength = Math.max(0, Math.min(200, Math.floor(length)));
    setDraftClusters((prev) => Array.from({ length: nextLength }, (_item, index) => prev[index] ?? null));
    setFocusedIndex((index) => Math.min(index, Math.max(0, nextLength - 1)));
  };

  const selectClusterForFocused = (clusterId: number) => {
    if (draftClusters.length === 0) return;
    setDraftClusters((prev) => prev.map((item, index) => (index === focusedIndex ? clusterId : item)));
  };

  const saveArray = () => {
    if (!canSave) return;
    mutate({
      action: "update_array",
      id: array.id,
      name: name.trim() || null,
      active,
      clusters: draftClusters,
    });
  };

  const deleteArray = () => {
    if (!window.confirm(`Delete array ${array.name ?? array.id}?`)) return;
    mutate({ action: "delete_array", id: array.id });
  };

  return (
    <Box className="glass" sx={{ p: 2, borderRadius: 2 }}>
      <Stack spacing={1.5}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1} sx={{ alignItems: { md: "center" } }}>
          <TextField
            label="Array name"
            size="small"
            value={name}
            onChange={(event) => setName(event.target.value)}
            sx={{ minWidth: 220 }}
          />
          <TextField
            label="Length"
            type="number"
            size="small"
            value={draftClusters.length}
            onChange={(event) => setLength(Number(event.target.value))}
            sx={{ width: 110 }}
            slotProps={{ htmlInput: { min: 0, max: 200 } }}
          />
          <FormControlLabel
            control={<Checkbox checked={active} onChange={(event) => setActive(event.target.checked)} />}
            label="Active"
            sx={{ whiteSpace: "nowrap" }}
          />
          <Chip
            color={lengthMatches ? "primary" : "warning"}
            label={lengthMatches ? "length ok" : `${sentence.char_count_no_spaces} chars needed`}
          />
          <Chip label={`${array.match_count} match${array.match_count === 1 ? "" : "es"}`} variant="outlined" />
          <Box sx={{ flex: 1 }} />
          <Button startIcon={<SaveIcon />} variant="contained" disabled={!canSave || mutationPending} onClick={saveArray}>
            Save Array
          </Button>
          <Tooltip title="Delete array">
            <IconButton color="error" onClick={deleteArray} disabled={mutationPending}>
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Stack>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(58px, 1fr))",
            gap: 0.75,
          }}
        >
          {draftClusters.map((clusterId, index) => (
            <Button
              key={`${array.id}-slot-${index}`}
              variant={focusedIndex === index ? "contained" : "outlined"}
              color={clusterId == null ? "warning" : "primary"}
              onClick={() => setFocusedIndex(index)}
              sx={{
                minWidth: 0,
                px: 0.5,
                display: "flex",
                flexDirection: "column",
                lineHeight: 1.1,
                aspectRatio: "1 / 1",
              }}
            >
              <Typography variant="caption" sx={{ fontSize: 10 }}>
                {index + 1} · {sentence.chars_no_spaces[index] ?? "?"}
              </Typography>
              <Typography sx={{ fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>
                {clusterId == null ? "—" : clusterLabel(clusterId)}
              </Typography>
            </Button>
          ))}
        </Box>

        <Divider />

        <Stack direction={{ xs: "column", md: "row" }} spacing={1} sx={{ alignItems: { md: "center" } }}>
          <Typography sx={{ fontWeight: 650 }}>
            Position {draftClusters.length === 0 ? "—" : focusedIndex + 1}
          </Typography>
          <TextField
            size="small"
            label="Search clusters"
            value={clusterSearch}
            onChange={(event) => setClusterSearch(event.target.value)}
            sx={{ minWidth: 240 }}
          />
          <Typography variant="caption" color="text.secondary">
            Click a cluster preview to assign it to the focused position.
          </Typography>
        </Stack>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(122px, 1fr))",
            gap: 1,
            maxHeight: 310,
            overflow: "auto",
            pr: 0.5,
          }}
        >
          {visibleClusters.map((cluster) => (
            <ClusterChoice
              key={cluster.cluster_id}
              cluster={cluster}
              selected={draftClusters[focusedIndex] === cluster.cluster_id}
              onClick={() => selectClusterForFocused(cluster.cluster_id)}
            />
          ))}
        </Box>

        <MatchPreviews matches={array.matches} />
      </Stack>
    </Box>
  );
}

function ClusterChoice({
  cluster,
  selected,
  onClick,
}: {
  cluster: ClusterSummary;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <Box
      component="button"
      type="button"
      onClick={onClick}
      sx={{
        p: 1,
        borderRadius: 1.5,
        border: selected ? "2px solid var(--color-glass-accent)" : "1px solid var(--color-glass-border)",
        background: "var(--color-glass-surface)",
        color: "inherit",
        cursor: "pointer",
        textAlign: "left",
      }}
    >
      <Stack spacing={0.5}>
        <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
          <Typography sx={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
            c{clusterLabel(cluster.cluster_id)}
          </Typography>
          <Chip size="small" label={cluster.active_count} sx={{ height: 18, fontSize: 10 }} />
        </Stack>
        <Box sx={{ minHeight: 50, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {cluster.sample_member ? (
            <MemberCrop
              imageUrl={cluster.sample_member.image_url}
              imageSize={cluster.sample_member.image_size}
              aabb={cluster.sample_member.aabb}
              displayHeight={46}
            />
          ) : (
            <Typography variant="caption" color="text.disabled">empty</Typography>
          )}
        </Box>
        <Typography className="coptic" sx={{ textAlign: "center", minHeight: 20, fontSize: 18 }}>
          {cluster.override_label ?? "—"}
        </Typography>
      </Stack>
    </Box>
  );
}

function MatchPreviews({ matches }: { matches: EditorialMatchPreview[] }) {
  return (
    <Stack spacing={1}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography sx={{ fontWeight: 650, flex: 1 }}>Matches</Typography>
        <Chip size="small" label={matches.length} />
      </Stack>
      {matches.length === 0 ? (
        <Typography variant="body2" color="text.secondary">No matches for this cluster array.</Typography>
      ) : (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
            gap: 1,
            maxHeight: 260,
            overflow: "auto",
            pr: 0.5,
          }}
        >
          {matches.map((match) => (
            <Box
              key={`${match.page}-${match.line_index}-${match.blob_ids.join("_")}`}
              sx={{ p: 1, borderRadius: 1.5, border: "1px solid var(--color-glass-border)" }}
            >
              <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", mb: 0.5 }}>
                <Typography variant="caption" sx={{ flex: 1 }}>
                  p{match.page} · line {match.line_index}
                </Typography>
                <Tooltip title="Open page">
                  <IconButton size="small" component={Link} href={`/review/${match.page}`} sx={{ p: 0.25 }}>
                    <LaunchIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </Tooltip>
              </Stack>
              <Box sx={{ display: "flex", justifyContent: "center", minHeight: 58 }}>
                <MemberCrop
                  imageUrl={match.image_url}
                  imageSize={match.image_size}
                  aabb={match.aabb}
                  displayHeight={54}
                  pad={8}
                />
              </Box>
              <Typography variant="caption" color="text.secondary">
                blobs {match.blob_ids.join(" ")}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Stack>
  );
}