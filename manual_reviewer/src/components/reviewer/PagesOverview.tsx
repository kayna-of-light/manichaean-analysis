"use client";

import {
  Box,
  Button,
  Chip,
  CircularProgress,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import { usePagesList } from "@/components/reviewer/hooks";
import Link from "next/link";

const clampProgress = (value: number) => Math.min(100, Math.max(0, value));

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
          {data.pages.map((p) => {
            const checked = p.done_lines + p.flagged_lines;
            const total = p.total_lines;
            const boundedChecked = total > 0 ? Math.min(checked, total) : checked;
            const progress = total > 0 ? clampProgress((boundedChecked / total) * 100) : 0;
            const allDone = total > 0 && boundedChecked >= total;
            return (
              <Button
                key={p.page}
                component={Link}
                href={`/review/${p.page}`}
                variant="outlined"
                sx={{
                  flexDirection: "column",
                  py: 1.5,
                  borderColor: allDone
                    ? "rgba(100,200,100,0.6)"
                    : p.flagged_lines > 0
                      ? "rgba(220,120,120,0.6)"
                      : "var(--color-glass-border)",
                }}
              >
                <Typography
                  sx={{ fontVariantNumeric: "tabular-nums", fontSize: 18 }}
                >
                  p{p.page}
                </Typography>
                {total > 0 && (
                  <LinearProgress
                    variant="determinate"
                    value={progress}
                    sx={{
                      width: "100%",
                      mt: 0.75,
                      height: 4,
                      borderRadius: 2,
                      backgroundColor: "rgba(255,255,255,0.1)",
                      "& .MuiLinearProgress-bar": {
                        backgroundColor: allDone
                          ? "rgba(100,200,100,0.8)"
                          : "rgba(140,180,255,0.7)",
                      },
                    }}
                  />
                )}
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
                  {total > 0 && checked > 0 && (
                    <Typography sx={{ fontSize: 9, opacity: 0.6, alignSelf: "center" }}>
                      {checked}/{total}
                    </Typography>
                  )}
                </Stack>
              </Button>
            );
          })}
        </Box>
      )}
    </Stack>
  );
}
