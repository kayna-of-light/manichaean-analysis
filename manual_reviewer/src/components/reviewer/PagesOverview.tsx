"use client";

import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import { usePagesList } from "@/components/reviewer/hooks";
import Link from "next/link";

export function PagesOverview() {
  const { data, isLoading } = usePagesList();

  return (
    <Stack spacing={2}>
      <Typography sx={{ opacity: 0.75, maxWidth: 720 }}>
        Pick a page to review. Each tile shows the page status and the counts
        of completed and flagged lines.
      </Typography>
      {isLoading && <CircularProgress />}
      {data && (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(110px, 1fr))",
            gap: 1,
          }}
        >
          {data.pages.map((p) => (
            <Button
              key={p.page}
              component={Link}
              href={`/review/${p.page}`}
              variant="outlined"
              sx={{
                flexDirection: "column",
                py: 1.5,
                borderColor:
                  p.flagged_lines > 0
                    ? "rgba(220,120,120,0.6)"
                    : "var(--color-glass-border)",
              }}
            >
              <Typography
                sx={{ fontVariantNumeric: "tabular-nums", fontSize: 18 }}
              >
                p{p.page}
              </Typography>
              <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }}>
                {p.done_lines > 0 && (
                  <Chip
                    size="small"
                    label={`${p.done_lines}✓`}
                    sx={{ height: 18, fontSize: 10 }}
                  />
                )}
                {p.flagged_lines > 0 && (
                  <Chip
                    size="small"
                    label={p.flagged_lines}
                    sx={{
                      height: 18,
                      fontSize: 10,
                      bgcolor: "rgba(220,120,120,0.2)",
                    }}
                  />
                )}
              </Stack>
            </Button>
          ))}
        </Box>
      )}
    </Stack>
  );
}
