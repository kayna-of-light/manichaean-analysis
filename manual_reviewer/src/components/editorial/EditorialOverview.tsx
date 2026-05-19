"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import LaunchIcon from "@mui/icons-material/Launch";

interface EditorialArrayView {
  id: number;
  match_count: number;
}

interface EditorialSentenceView {
  id: number;
  text: string;
  active: number;
  note: string | null;
  char_count_no_spaces: number;
  arrays: EditorialArrayView[];
}

export function EditorialOverview() {
  const editorialQuery = useQuery<{ sentences: EditorialSentenceView[] }>({
    queryKey: ["editorial"],
    queryFn: async () => {
      const res = await fetch("/api/editorial");
      if (!res.ok) throw new Error("editorial fetch failed");
      return res.json();
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
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="h6" sx={{ flex: 1 }}>Editorial Sentences</Typography>
        <Chip label={`${sentences.length} sentences`} />
        <Chip label={`${totalMatches} matches`} variant="outlined" />
        <Button
          variant="contained"
          endIcon={<LaunchIcon />}
          component={Link}
          href="/editorial"
        >
          Open Editor
        </Button>
      </Stack>

      <Stack spacing={1} sx={{ maxHeight: 600, overflow: "auto", pr: 0.5 }}>
        {sentences.map((sentence) => {
          const arrayMatchTotal = sentence.arrays.reduce((a, arr) => a + arr.match_count, 0);
          return (
            <Box
              key={sentence.id}
              className="glass"
              sx={{ p: 1.25, borderRadius: 2, cursor: "pointer", "&:hover": { opacity: 0.85 } }}
              component={Link}
              href={`/editorial/${sentence.id}`}
            >
              <Stack direction="row" spacing={0.75} sx={{ alignItems: "center" }}>
                <Typography sx={{ fontWeight: 650, flex: 1 }}>{sentence.text}</Typography>
                <Chip size="small" label={sentence.active ? "on" : "off"} color={sentence.active ? "primary" : "default"} />
                <Chip size="small" label={`${arrayMatchTotal} match${arrayMatchTotal === 1 ? "" : "es"}`} variant="outlined" />
              </Stack>
            </Box>
          );
        })}
      </Stack>
    </Stack>
  );
}