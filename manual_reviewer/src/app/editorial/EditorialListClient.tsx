"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutlined";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import LaunchIcon from "@mui/icons-material/Launch";
import { CreateSentenceDialog } from "@/components/editorial/CreateSentenceDialog";

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

export function EditorialListClient() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const editorialQuery = useQuery<{ sentences: EditorialSentenceView[] }>({
    queryKey: ["editorial"],
    queryFn: async () => {
      const res = await fetch("/api/editorial");
      if (!res.ok) throw new Error("editorial fetch failed");
      return res.json();
    },
  });

  const mutation = useMutation({
    mutationFn: async (action: Record<string, unknown>) => {
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
    },
  });

  const sentences = editorialQuery.data?.sentences ?? [];
  const totalMatches = sentences.reduce(
    (sum, s) => sum + s.arrays.reduce((a, arr) => a + arr.match_count, 0),
    0,
  );

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
    <Box sx={{ maxWidth: 1300, mx: "auto" }}>
      <Paper elevation={0} sx={{ p: 4, borderRadius: 4 }}>
        <Stack spacing={3}>
          {/* Header */}
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Tooltip title="Back to home">
              <IconButton component={Link} href="/">
                <ArrowBackIcon />
              </IconButton>
            </Tooltip>
            <Box sx={{ flex: 1 }}>
              <Typography variant="overline" sx={{ opacity: 0.7 }}>
                Manual Reviewer
              </Typography>
              <Typography variant="h4">Editorial Sentences</Typography>
            </Box>
            <Chip label={`${sentences.length} sentences`} />
            <Chip label={`${totalMatches} matches`} variant="outlined" />
            <Button
              startIcon={<AddCircleOutlineIcon />}
              variant="contained"
              onClick={() => setCreateOpen(true)}
            >
              Add Sentence
            </Button>
          </Stack>

          {/* Sentence list */}
          <Stack spacing={1.5}>
            {sentences.map((sentence) => {
              const arrayMatchTotal = sentence.arrays.reduce((a, arr) => a + arr.match_count, 0);
              return (
                <Box
                  key={sentence.id}
                  className="glass"
                  sx={{ p: 2, borderRadius: 2, cursor: "pointer", "&:hover": { opacity: 0.85 } }}
                  component={Link}
                  href={`/editorial/${sentence.id}`}
                >
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                    <Typography sx={{ fontWeight: 650, flex: 1 }}>{sentence.text}</Typography>
                    <Chip
                      size="small"
                      label={sentence.active ? "on" : "off"}
                      color={sentence.active ? "primary" : "default"}
                    />
                    <Chip
                      size="small"
                      label={`${sentence.char_count_no_spaces} chars`}
                      variant="outlined"
                    />
                    <Chip
                      size="small"
                      label={`${sentence.arrays.length} array${sentence.arrays.length === 1 ? "" : "s"}`}
                      variant="outlined"
                    />
                    <Chip
                      size="small"
                      label={`${arrayMatchTotal} match${arrayMatchTotal === 1 ? "" : "es"}`}
                      variant="outlined"
                    />
                    <Tooltip title="Open detail">
                      <IconButton size="small" sx={{ p: 0.25 }}>
                        <LaunchIcon sx={{ fontSize: 16 }} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                  {sentence.note && (
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                      {sentence.note}
                    </Typography>
                  )}
                </Box>
              );
            })}
          </Stack>
        </Stack>
      </Paper>

      <CreateSentenceDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={(text, note) => {
          mutation.mutate(
            { action: "create_sentence", text, active: true, note: note || null },
            { onSuccess: () => setCreateOpen(false) },
          );
        }}
        busy={mutation.isPending}
      />
    </Box>
  );
}
