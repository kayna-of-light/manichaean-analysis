"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutlined";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CloseIcon from "@mui/icons-material/Close";
import DeleteIcon from "@mui/icons-material/Delete";
import LaunchIcon from "@mui/icons-material/Launch";
import SaveIcon from "@mui/icons-material/Save";
import { MemberCrop } from "@/components/cluster/MemberCrop";
import { CreateArrayDialog } from "@/components/editorial/CreateArrayDialog";

// ─── Types ───────────────────────────────────────────────────────────────────

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
  min_length: number | null;
  max_length: number | null;
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
  | { action: "update_sentence"; id: number; text?: string; active?: boolean; note?: string | null }
  | { action: "delete_sentence"; id: number }
  | { action: "create_array"; sentence_id: number; name?: string | null; clusters: number[]; active?: boolean; min_length?: number | null; max_length?: number | null }
  | { action: "update_array"; id: number; name?: string | null; clusters?: number[]; active?: boolean; min_length?: number | null; max_length?: number | null }
  | { action: "delete_array"; id: number };

const WILDCARD_SINGLE = -2;
const WILDCARD_MULTI = -3;

function clusterLabel(id: number): string {
  if (id === WILDCARD_SINGLE) return ".";
  if (id === WILDCARD_MULTI) return "*";
  return id < 0 ? String(id) : String(id).padStart(3, "0");
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function EditorialSentenceClient({ sentenceId }: { sentenceId: number }) {
  const qc = useQueryClient();
  const router = useRouter();

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
  const sentence = sentences.find((s) => s.id === sentenceId) ?? null;
  const clusters = clustersQuery.data?.clusters ?? [];

  if (editorialQuery.isLoading) {
    return (
      <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!sentence) {
    return (
      <Box sx={{ maxWidth: 1300, mx: "auto" }}>
        <Paper elevation={0} sx={{ p: 4, borderRadius: 4 }}>
          <Typography color="error">Sentence #{sentenceId} not found.</Typography>
          <Button component={Link} href="/editorial" sx={{ mt: 2 }}>Back to list</Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 1300, mx: "auto" }}>
      <Paper elevation={0} sx={{ p: 4, borderRadius: 4 }}>
        <Stack spacing={3}>
          {/* Header */}
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Tooltip title="Back to editorial list">
              <IconButton component={Link} href="/editorial">
                <ArrowBackIcon />
              </IconButton>
            </Tooltip>
            <Box sx={{ flex: 1 }}>
              <Typography variant="overline" sx={{ opacity: 0.7 }}>
                Editorial Sentence #{sentence.id}
              </Typography>
              <Typography variant="h4">{sentence.text}</Typography>
            </Box>
          </Stack>

          {/* Sentence editor */}
          <SentenceEditor
            sentence={sentence}
            clusters={clusters}
            mutationPending={mutation.isPending}
            mutate={(action) => mutation.mutate(action)}
            onDeleted={() => router.push("/editorial")}
          />
        </Stack>
      </Paper>
    </Box>
  );
}

// ─── Sentence Editor ─────────────────────────────────────────────────────────

function SentenceEditor({
  sentence,
  clusters,
  mutationPending,
  mutate,
  onDeleted,
}: {
  sentence: EditorialSentenceView;
  clusters: ClusterSummary[];
  mutationPending: boolean;
  mutate: (action: EditorialAction) => void;
  onDeleted: () => void;
}) {
  const [text, setText] = useState(sentence.text);
  const [note, setNote] = useState(sentence.note ?? "");
  const [active, setActive] = useState(Boolean(sentence.active));
  const [createArrayOpen, setCreateArrayOpen] = useState(false);

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
    onDeleted();
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
              onChange={(e) => setText(e.target.value)}
              fullWidth
            />
            <FormControlLabel
              control={<Checkbox checked={active} onChange={(e) => setActive(e.target.checked)} />}
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
            onChange={(e) => setNote(e.target.value)}
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
        <Button startIcon={<AddCircleOutlineIcon />} onClick={() => setCreateArrayOpen(true)} disabled={mutationPending}>
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

      <CreateArrayDialog
        open={createArrayOpen}
        sentenceId={sentence.id}
        onClose={() => setCreateArrayOpen(false)}
        onSubmit={(name) => {
          mutate({
            action: "create_array",
            sentence_id: sentence.id,
            name: name || null,
            clusters: [],
            active: true,
          });
          setCreateArrayOpen(false);
        }}
        busy={mutationPending}
      />
    </Stack>
  );
}

// ─── Cluster Array Editor ────────────────────────────────────────────────────

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
  const [pickerIndex, setPickerIndex] = useState<number | null>(null);
  const [minLength, setMinLength] = useState<string>(
    array.min_length != null ? String(array.min_length) : String(array.cluster_array.length || ""),
  );
  const [maxLength, setMaxLength] = useState<string>(
    array.max_length != null ? String(array.max_length) : String(array.cluster_array.length || ""),
  );

  useEffect(() => {
    setName(array.name ?? "");
    setActive(Boolean(array.active));
    setDraftClusters(array.cluster_array);
    setMinLength(array.min_length != null ? String(array.min_length) : String(array.cluster_array.length || ""));
    setMaxLength(array.max_length != null ? String(array.max_length) : String(array.cluster_array.length || ""));
  }, [array.id, array.name, array.active, array.cluster_array, array.min_length, array.max_length]);

  const parseIntOrNull = (v: string): number | null => {
    const n = parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : null;
  };

  const minLenVal = parseIntOrNull(minLength);
  const maxLenVal = parseIntOrNull(maxLength);
  const allPositionsSet = draftClusters.every((item): item is number => Number.isInteger(item));
  const lengthInBounds =
    (minLenVal == null || draftClusters.length >= minLenVal) &&
    (maxLenVal == null || draftClusters.length <= maxLenVal);
  const canSave = allPositionsSet && draftClusters.length > 0 && lengthInBounds;

  const insertAt = (index: number) => {
    setDraftClusters((prev) => {
      const next = [...prev];
      next.splice(index, 0, null);
      return next;
    });
  };

  const removeAt = (index: number) => {
    setDraftClusters((prev) => prev.filter((_, i) => i !== index));
  };

  const setClusterAt = (index: number, clusterId: number) => {
    setDraftClusters((prev) => prev.map((item, i) => (i === index ? clusterId : item)));
  };

  const saveArray = () => {
    if (!canSave) return;
    mutate({
      action: "update_array",
      id: array.id,
      name: name.trim() || null,
      active,
      clusters: draftClusters as number[],
      min_length: parseIntOrNull(minLength),
      max_length: parseIntOrNull(maxLength),
    });
  };

  const deleteArray = () => {
    if (!window.confirm(`Delete array ${array.name ?? array.id}?`)) return;
    mutate({ action: "delete_array", id: array.id });
  };

  return (
    <Box className="glass" sx={{ p: 2, borderRadius: 2 }}>
      <Stack spacing={1.5}>
        {/* Header row */}
        <Stack direction={{ xs: "column", md: "row" }} spacing={1} sx={{ alignItems: { md: "center" }, flexWrap: "wrap", rowGap: 1 }}>
          <TextField
            label="Array name"
            size="small"
            value={name}
            onChange={(e) => setName(e.target.value)}
            sx={{ minWidth: 180 }}
          />
          <TextField
            label="Min length"
            type="number"
            size="small"
            value={minLength}
            onChange={(e) => setMinLength(e.target.value)}
            sx={{ width: 100 }}
            slotProps={{ htmlInput: { min: 1, max: 200 } }}
          />
          <TextField
            label="Max length"
            type="number"
            size="small"
            value={maxLength}
            onChange={(e) => setMaxLength(e.target.value)}
            sx={{ width: 100 }}
            slotProps={{ htmlInput: { min: 1, max: 200 } }}
          />
          <FormControlLabel
            control={<Checkbox checked={active} onChange={(e) => setActive(e.target.checked)} />}
            label="Active"
            sx={{ whiteSpace: "nowrap" }}
          />
          <Chip
            size="small"
            label={`${draftClusters.length} slots`}
            color={lengthInBounds ? "primary" : "error"}
          />
          <Chip label={`${array.match_count} match${array.match_count === 1 ? "" : "es"}`} variant="outlined" size="small" />
          <Box sx={{ flex: 1 }} />
          <Button startIcon={<SaveIcon />} variant="contained" disabled={!canSave || mutationPending} onClick={saveArray}>
            Save
          </Button>
          <Tooltip title="Delete array">
            <IconButton color="error" onClick={deleteArray} disabled={mutationPending}>
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Stack>

        {/* Pattern strip with hover add/remove */}
        <PatternStrip
          draftClusters={draftClusters}
          sentence={sentence}
          clusters={clusters}
          onInsert={insertAt}
          onRemove={removeAt}
          onSlotClick={(index) => setPickerIndex(index)}
        />

        {!lengthInBounds && (
          <Typography variant="caption" color="error">
            Current length ({draftClusters.length}) is outside bounds [{minLength || "?"}, {maxLength || "?"}].
          </Typography>
        )}

        {/* Match previews */}
        <MatchPreviews matches={array.matches} />
      </Stack>

      {/* Cluster picker dialog */}
      <SelectClusterDialog
        open={pickerIndex != null}
        clusters={clusters}
        currentValue={pickerIndex != null ? draftClusters[pickerIndex] : null}
        position={pickerIndex != null ? pickerIndex + 1 : 0}
        charHint={pickerIndex != null ? sentence.chars_no_spaces[pickerIndex] ?? null : null}
        onSelect={(clusterId) => {
          if (pickerIndex != null) setClusterAt(pickerIndex, clusterId);
          setPickerIndex(null);
        }}
        onClose={() => setPickerIndex(null)}
      />
    </Box>
  );
}

// ─── Pattern Strip ───────────────────────────────────────────────────────────

function PatternStrip({
  draftClusters,
  sentence,
  clusters,
  onInsert,
  onRemove,
  onSlotClick,
}: {
  draftClusters: (number | null)[];
  sentence: EditorialSentenceView;
  clusters: ClusterSummary[];
  onInsert: (index: number) => void;
  onRemove: (index: number) => void;
  onSlotClick: (index: number) => void;
}) {
  const [hoverGap, setHoverGap] = useState<number | null>(null);
  const [hoverSlot, setHoverSlot] = useState<number | null>(null);

  const clusterMap = useMemo(() => {
    const map = new Map<number, ClusterSummary>();
    for (const c of clusters) map.set(c.cluster_id, c);
    return map;
  }, [clusters]);

  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 0,
        py: 1,
        minHeight: 72,
      }}
    >
      {/* Leading inserter */}
      <InsertGap
        index={0}
        visible={hoverGap === 0}
        onMouseEnter={() => setHoverGap(0)}
        onMouseLeave={() => setHoverGap(null)}
        onInsert={() => onInsert(0)}
      />

      {draftClusters.map((clusterId, index) => {
        const cluster = clusterId != null ? clusterMap.get(clusterId) : null;
        return (
          <Box key={index} sx={{ display: "flex", alignItems: "center" }}>
            <SlotBox
              index={index}
              clusterId={clusterId}
              cluster={cluster ?? null}
              charHint={sentence.chars_no_spaces[index] ?? null}
              showDelete={hoverSlot === index}
              onMouseEnter={() => setHoverSlot(index)}
              onMouseLeave={() => setHoverSlot(null)}
              onClick={() => onSlotClick(index)}
              onDelete={() => onRemove(index)}
            />
            <InsertGap
              index={index + 1}
              visible={hoverGap === index + 1}
              onMouseEnter={() => setHoverGap(index + 1)}
              onMouseLeave={() => setHoverGap(null)}
              onInsert={() => onInsert(index + 1)}
            />
          </Box>
        );
      })}

      {draftClusters.length === 0 && (
        <Button
          size="small"
          startIcon={<AddIcon />}
          onClick={() => onInsert(0)}
          sx={{ ml: 1 }}
        >
          Add slot
        </Button>
      )}
    </Box>
  );
}

function InsertGap({
  index,
  visible,
  onMouseEnter,
  onMouseLeave,
  onInsert,
}: {
  index: number;
  visible: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onInsert: () => void;
}) {
  return (
    <Box
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      sx={{
        width: 24,
        height: 64,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <IconButton
        size="small"
        color="primary"
        onClick={(e) => {
          e.stopPropagation();
          onInsert();
        }}
        sx={{
          width: 22,
          height: 22,
          p: 0,
          opacity: visible ? 1 : 0.25,
          transition: "opacity 0.15s",
          "&:hover": { opacity: 1 },
        }}
      >
        <AddIcon sx={{ fontSize: 16 }} />
      </IconButton>
    </Box>
  );
}

function SlotBox({
  index,
  clusterId,
  cluster,
  charHint,
  showDelete,
  onMouseEnter,
  onMouseLeave,
  onClick,
  onDelete,
}: {
  index: number;
  clusterId: number | null;
  cluster: ClusterSummary | null;
  charHint: string | null;
  showDelete: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onClick: () => void;
  onDelete: () => void;
}) {
  const isWildcard = clusterId === WILDCARD_SINGLE || clusterId === WILDCARD_MULTI;
  const isEmpty = clusterId == null;

  return (
    <Box
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
      sx={{
        position: "relative",
        width: 56,
        height: 64,
        border: isEmpty
          ? "2px dashed var(--color-glass-border)"
          : isWildcard
            ? "2px solid var(--mui-palette-info-main)"
            : "1px solid var(--color-glass-border)",
        borderRadius: 1.5,
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: isEmpty ? "transparent" : "var(--color-glass-surface)",
        transition: "border-color 0.15s",
        "&:hover": {
          borderColor: "var(--color-glass-accent)",
        },
        flexShrink: 0,
      }}
    >
      {/* Position + char hint */}
      <Typography variant="caption" sx={{ fontSize: 9, opacity: 0.7, lineHeight: 1 }}>
        {index + 1}{charHint ? ` · ${charHint}` : ""}
      </Typography>

      {/* Cluster label/preview */}
      {isEmpty ? (
        <Typography sx={{ fontSize: 18, fontWeight: 700, opacity: 0.3 }}>?</Typography>
      ) : isWildcard ? (
        <Typography sx={{ fontSize: 20, fontWeight: 700, color: "var(--mui-palette-info-main)" }}>
          {clusterLabel(clusterId)}
        </Typography>
      ) : (
        <>
          <Typography sx={{ fontSize: 11, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
            {clusterLabel(clusterId)}
          </Typography>
          {cluster?.override_label && (
            <Typography className="coptic" sx={{ fontSize: 14, lineHeight: 1 }}>
              {cluster.override_label}
            </Typography>
          )}
        </>
      )}

      {/* Delete button on hover */}
      {showDelete && (
        <IconButton
          size="small"
          color="error"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          sx={{
            position: "absolute",
            top: -8,
            right: -8,
            width: 18,
            height: 18,
            p: 0,
            bgcolor: "background.paper",
            border: "1px solid",
            borderColor: "error.main",
            "&:hover": { bgcolor: "error.main", color: "white" },
          }}
        >
          <CloseIcon sx={{ fontSize: 12 }} />
        </IconButton>
      )}
    </Box>
  );
}

// ─── Select Cluster Dialog ───────────────────────────────────────────────────

function SelectClusterDialog({
  open,
  clusters,
  currentValue,
  position,
  charHint,
  onSelect,
  onClose,
}: {
  open: boolean;
  clusters: ClusterSummary[];
  currentValue: number | null;
  position: number;
  charHint: string | null;
  onSelect: (clusterId: number) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (open) setSearch("");
  }, [open]);

  const filtered = useMemo(() => {
    const list = clusters.filter((c) => c.active_count > 0 || c.cluster_id < 0);
    const term = search.trim().toLowerCase();
    if (!term) return list.slice(0, 150);
    return list
      .filter((c) =>
        `${c.cluster_id} ${clusterLabel(c.cluster_id)} ${c.override_label ?? ""}`.toLowerCase().includes(term),
      )
      .slice(0, 150);
  }, [clusters, search]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Select cluster for position {position}
        {charHint ? ` (char: ${charHint})` : ""}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {/* Wildcard options */}
          <Stack direction="row" spacing={1}>
            <Button
              variant={currentValue === WILDCARD_SINGLE ? "contained" : "outlined"}
              color="info"
              onClick={() => onSelect(WILDCARD_SINGLE)}
            >
              . (single wildcard)
            </Button>
            <Button
              variant={currentValue === WILDCARD_MULTI ? "contained" : "outlined"}
              color="info"
              onClick={() => onSelect(WILDCARD_MULTI)}
            >
              * (multi wildcard)
            </Button>
          </Stack>

          <Divider />

          {/* Search */}
          <TextField
            label="Search clusters"
            size="small"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            fullWidth
            autoFocus
          />

          {/* Cluster grid */}
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(110px, 1fr))",
              gap: 1,
              maxHeight: 400,
              overflow: "auto",
              pr: 0.5,
            }}
          >
            {filtered.map((cluster) => (
              <Box
                key={cluster.cluster_id}
                component="button"
                type="button"
                onClick={() => onSelect(cluster.cluster_id)}
                sx={{
                  p: 1,
                  borderRadius: 1.5,
                  border:
                    currentValue === cluster.cluster_id
                      ? "2px solid var(--color-glass-accent)"
                      : "1px solid var(--color-glass-border)",
                  background: "var(--color-glass-surface)",
                  color: "inherit",
                  cursor: "pointer",
                  textAlign: "center",
                }}
              >
                <Stack spacing={0.25} sx={{ alignItems: "center" }}>
                  <Typography sx={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", fontSize: 12 }}>
                    c{clusterLabel(cluster.cluster_id)}
                  </Typography>
                  <Box sx={{ minHeight: 40, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    {cluster.sample_member ? (
                      <MemberCrop
                        imageUrl={cluster.sample_member.image_url}
                        imageSize={cluster.sample_member.image_size}
                        aabb={cluster.sample_member.aabb}
                        displayHeight={36}
                      />
                    ) : (
                      <Typography variant="caption" color="text.disabled">—</Typography>
                    )}
                  </Box>
                  {cluster.override_label && (
                    <Typography className="coptic" sx={{ fontSize: 16 }}>
                      {cluster.override_label}
                    </Typography>
                  )}
                  <Chip size="small" label={cluster.active_count} sx={{ height: 16, fontSize: 9 }} />
                </Stack>
              </Box>
            ))}
          </Box>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

// ─── Match Previews ──────────────────────────────────────────────────────────

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
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
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
                  p{match.page} · line {match.line_index} · {match.token_count} tokens
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
                  maxDisplayWidth={200}
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
