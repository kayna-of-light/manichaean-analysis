"use client";
import {
  Box,
  Chip,
  CircularProgress,
  List,
  ListItemButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useMemo, useState } from "react";
import { usePagesList } from "./hooks";

export function PageNavigator() {
  const { data, isLoading } = usePagesList();
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    if (!data) return [];
    if (!q.trim()) return data.pages;
    return data.pages.filter((p) => p.page.includes(q.trim()));
  }, [data, q]);

  return (
    <Box className="glass" sx={{ width: 240, p: 2, height: "100%", overflowY: "auto" }}>
      <Typography variant="overline" color="text.secondary">Pages</Typography>
      <TextField
        size="small"
        fullWidth
        placeholder="filter by page id…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        sx={{ my: 1 }}
      />
      {isLoading && <CircularProgress size={20} />}
      <List dense disablePadding>
        {filtered.map((p) => (
          <ListItemButton
            key={p.page}
            component={Link}
            href={`/review/${p.page}`}
            sx={{ borderRadius: 1, mb: 0.5 }}
          >
            <Stack direction="row" spacing={1} sx={{ flex: 1, alignItems: "center" }}>
              <Typography sx={{ fontVariantNumeric: "tabular-nums" }}>p{p.page}</Typography>
              <Box sx={{ flex: 1 }} />
              {p.flagged_lines > 0 && (
                <Chip
                  size="small"
                  label={p.flagged_lines}
                  sx={{ height: 18, fontSize: 10, bgcolor: "rgba(220,120,120,0.2)" }}
                />
              )}
              {p.special_lines > 0 && (
                <Chip
                  size="small"
                  label={`${p.special_lines}★`}
                  sx={{ height: 18, fontSize: 10, bgcolor: "rgba(245,205,90,0.18)" }}
                />
              )}
              {p.done_lines > 0 && (
                <Chip
                  size="small"
                  label={`${p.done_lines}✓`}
                  sx={{ height: 18, fontSize: 10, bgcolor: "rgba(120,200,140,0.15)" }}
                />
              )}
              <Chip
                size="small"
                label={p.status}
                sx={{ height: 18, fontSize: 10 }}
              />
            </Stack>
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
}
