"use client";

import * as React from "react";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import Box from "@mui/material/Box";
import Tooltip from "@mui/material/Tooltip";
import Snackbar from "@mui/material/Snackbar";
import Alert from "@mui/material/Alert";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import BackupOutlinedIcon from "@mui/icons-material/BackupOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import Link from "next/link";
import { useThemeMode } from "../theme/ThemeProvider";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { mode, toggle } = useThemeMode();
  const [snack, setSnack] = React.useState<{ msg: string; ok: boolean } | null>(
    null,
  );

  const trigger = async (url: string, label: string) => {
    try {
      const res = await fetch(url, { method: "POST" });
      const json = (await res.json()) as { ok?: boolean; target?: string; error?: string };
      if (json.ok) setSnack({ msg: `${label}: ${json.target ?? "done"}`, ok: true });
      else setSnack({ msg: `${label} failed: ${json.error ?? "error"}`, ok: false });
    } catch (e) {
      setSnack({ msg: `${label} failed: ${(e as Error).message}`, ok: false });
    }
  };

  return (
    <Box sx={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      <AppBar position="sticky">
        <Toolbar sx={{ gap: 2 }}>
          <IconButton component={Link} href="/" size="small" aria-label="home">
            <HomeOutlinedIcon fontSize="small" />
          </IconButton>
          <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.01em" }}>
            Kephalaia · Manual Reviewer
          </Typography>
          <Typography
            variant="caption"
            sx={{ opacity: 0.65, ml: 1, fontFamily: "var(--font-mono)" }}
          >
            v0.1
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Tooltip title="Export edits to JSON">
            <IconButton
              size="small"
              aria-label="export"
              onClick={() => trigger("/api/export", "Export")}
            >
              <FileDownloadOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Trigger backup">
            <IconButton
              size="small"
              aria-label="backup"
              onClick={() => trigger("/api/backup", "Backup")}
            >
              <BackupOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={mode === "dark" ? "Light mode" : "Dark mode"}>
            <IconButton size="small" onClick={toggle} aria-label="toggle theme">
              {mode === "dark" ? (
                <LightModeOutlinedIcon fontSize="small" />
              ) : (
                <DarkModeOutlinedIcon fontSize="small" />
              )}
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ flex: 1, p: 3 }}>
        {children}
      </Box>
      <Snackbar
        open={Boolean(snack)}
        autoHideDuration={4000}
        onClose={() => setSnack(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        {snack ? (
          <Alert severity={snack.ok ? "success" : "error"} variant="filled">
            {snack.msg}
          </Alert>
        ) : undefined}
      </Snackbar>
    </Box>
  );
}
