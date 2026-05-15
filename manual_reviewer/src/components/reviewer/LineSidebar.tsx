"use client";
import { Box, Chip, List, ListItemButton, Typography } from "@mui/material";
import FlagIcon from "@mui/icons-material/Flag";
import type { ReviewLine } from "./hooks";

interface Props {
  lines: ReviewLine[];
  selectedIndex: number | null;
  onSelect: (idx: number) => void;
}

function statusColor(status: string): { bg: string; fg: string } {
  switch (status) {
    case "done":
      return { bg: "rgba(120,200,140,0.15)", fg: "rgb(140,210,160)" };
    case "in_progress":
      return { bg: "rgba(200,164,101,0.15)", fg: "var(--color-glass-accent)" };
    case "flagged":
      return { bg: "rgba(220,120,120,0.18)", fg: "rgb(230,140,140)" };
    default:
      return { bg: "var(--color-glass-surface)", fg: "var(--color-glass-muted)" };
  }
}

export function LineSidebar({ lines, selectedIndex, onSelect }: Props) {
  return (
    <Box
      className="glass"
      sx={{
        width: 220,
        flexShrink: 0,
        height: "100%",
        overflowY: "auto",
        p: 1.5,
      }}
    >
      <Typography variant="overline" color="text.secondary">
        Lines ({lines.length})
      </Typography>
      <List dense disablePadding sx={{ mt: 1 }}>
        {lines.map((l) => {
          const review = l.tokens.filter((t) => t.review).length;
          const edited = l.tokens.filter((t) => t.user_modified).length;
          const c = statusColor(l.status);
          return (
            <ListItemButton
              key={l.line_index}
              selected={selectedIndex === l.line_index}
              onClick={() => onSelect(l.line_index)}
              sx={{
                borderRadius: 1,
                mb: 0.5,
                "&.Mui-selected": {
                  bgcolor: "rgba(200,164,101,0.12)",
                  border: "1px solid var(--color-glass-accent)",
                },
              }}
            >
              <Box sx={{ flex: 1 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <Typography sx={{ fontVariantNumeric: "tabular-nums" }} variant="body2">
                    {String(l.line_index).padStart(2, "0")}
                  </Typography>
                  {l.status === "flagged" && (
                    <FlagIcon sx={{ fontSize: 14, color: c.fg }} />
                  )}
                  <Box sx={{ flex: 1 }} />
                  <Chip
                    size="small"
                    label={l.status}
                    sx={{
                      height: 18,
                      fontSize: 10,
                      bgcolor: c.bg,
                      color: c.fg,
                      borderRadius: 1,
                    }}
                  />
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {l.tokens.length} tokens · {review} review · {edited} edits
                </Typography>
              </Box>
            </ListItemButton>
          );
        })}
      </List>
    </Box>
  );
}
