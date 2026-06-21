"use client";
import { Box, Chip, List, ListItemButton, Typography } from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import FlagIcon from "@mui/icons-material/Flag";
import StarIcon from "@mui/icons-material/Star";
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
    case "special":
      return { bg: "rgba(245,205,90,0.18)", fg: "var(--color-status-special)" };
    default:
      return { bg: "var(--color-glass-surface)", fg: "var(--color-glass-muted)" };
  }
}

function StatusMarker({ status, color }: { status: string; color: string }) {
  return (
    <Box sx={{ width: 16, display: "flex", alignItems: "center", justifyContent: "center" }}>
      {status === "done" && <CheckCircleIcon sx={{ fontSize: 14, color }} />}
      {status === "flagged" && <FlagIcon sx={{ fontSize: 14, color }} />}
      {status === "special" && <StarIcon sx={{ fontSize: 14, color }} />}
    </Box>
  );
}

export function LineSidebar({ lines, selectedIndex, onSelect }: Props) {
  return (
    <Box
      className="glass"
      sx={{
        width: 156,
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
          const displayIndex = l.display_index ?? l.line_index;
          const edited = l.tokens.filter((t) => t.user_modified).length;
          const c = statusColor(l.status);
          return (
            <ListItemButton
              key={l.line_index}
              selected={selectedIndex === l.line_index}
              onClick={() => onSelect(l.line_index)}
              title={`Line ${displayIndex}: ${l.status}; ${edited} edits`}
              sx={{
                borderRadius: 1,
                mb: 0.5,
                minHeight: 30,
                px: 0.75,
                py: 0.5,
                overflow: "hidden",
                border: "1px solid transparent",
                bgcolor: l.status === "done" || l.status === "flagged" || l.status === "special" ? c.bg : undefined,
                "&.Mui-selected": {
                  bgcolor: "rgba(200,164,101,0.12)",
                  border: "1px solid var(--color-glass-accent)",
                },
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, width: "100%", minWidth: 0 }}>
                <StatusMarker status={l.status} color={c.fg} />
                <Typography sx={{ fontVariantNumeric: "tabular-nums", minWidth: 20 }} variant="body2">
                  {String(displayIndex).padStart(2, "0")}
                </Typography>
                <Box sx={{ flex: 1, minWidth: 0 }} />
                {edited > 0 && (
                  <Chip
                    size="small"
                    label={`${edited}e`}
                    sx={{
                      height: 16,
                      fontSize: 10,
                      bgcolor: "rgba(200,164,101,0.18)",
                      borderRadius: 0.75,
                      "& .MuiChip-label": { px: 0.5 },
                    }}
                  />
                )}
              </Box>
            </ListItemButton>
          );
        })}
      </List>
    </Box>
  );
}
