"use client";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { usePagesList } from "@/components/reviewer/hooks";
import Link from "next/link";

export default function Page() {
  const { data, isLoading } = usePagesList();

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      <Paper elevation={0} sx={{ p: 4, borderRadius: 4 }}>
        <Stack spacing={2}>
          <Box>
            <Typography variant="overline" sx={{ opacity: 0.7 }}>
              Manual Reviewer
            </Typography>
            <Typography variant="h3" sx={{ mt: 0.5 }}>
              Kephalaia · pages
            </Typography>
            <Typography sx={{ mt: 1, opacity: 0.75, maxWidth: 720 }}>
              Pick a page to review. Each tile shows the page status and the
              counts of completed and flagged lines.
            </Typography>
          </Box>
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
      </Paper>
    </Box>
  );
}
