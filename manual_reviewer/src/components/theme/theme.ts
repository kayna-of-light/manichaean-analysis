"use client";

import { createTheme } from "@mui/material/styles";

const accent = "#c8a465";

export function buildTheme(mode: "light" | "dark") {
  const isDark = mode === "dark";
  // rgb() is required so MUI 9 can derive *Channel tokens for alpha
  // computation. oklch() values trigger console warnings and silently
  // suppress translucent variants (faint outlined buttons).
  const textPrimary = isDark ? "rgb(244,241,232)" : "rgb(36,35,42)";
  const textSecondary = isDark ? "rgb(178,170,158)" : "rgb(98,96,108)";
  return createTheme({
    cssVariables: {
      colorSchemeSelector: "data-theme",
    },
    colorSchemes: {
      light: {
        palette: {
          primary: { main: accent, contrastText: "#1a1410" },
          secondary: { main: "#6f87b0" },
          error: { main: "#d32f2f" },
          warning: { main: "#ed6c02" },
          info: { main: "#0288d1" },
          success: { main: "#2e7d32" },
          background: {
            default: "rgba(250,248,244,0.0)",
            paper: "rgba(255,255,255,0.55)",
          },
          text: {
            primary: "rgb(36,35,42)",
            secondary: "rgb(98,96,108)",
            disabled: "rgba(36,35,42,0.38)",
          },
          action: {
            active: "rgb(36,35,42)",
            disabled: "rgba(36,35,42,0.26)",
            hover: "rgba(36,35,42,0.05)",
            selected: "rgba(200,164,101,0.12)",
          },
          divider: "rgba(0,0,0,0.12)",
        },
      },
      dark: {
        palette: {
          primary: { main: accent, contrastText: "#1a1410" },
          secondary: { main: "#6f87b0" },
          error: { main: "#f44336" },
          warning: { main: "#ffa726" },
          info: { main: "#29b6f6" },
          success: { main: "#66bb6a" },
          background: {
            default: "rgba(20,18,24,0.0)",
            paper: "rgba(255,255,255,0.05)",
          },
          text: {
            primary: "rgb(244,241,232)",
            secondary: "rgb(178,170,158)",
            disabled: "rgba(244,241,232,0.38)",
          },
          action: {
            active: "rgb(244,241,232)",
            disabled: "rgba(244,241,232,0.30)",
            hover: "rgba(244,241,232,0.08)",
            selected: "rgba(200,164,101,0.18)",
          },
          divider: "rgba(255,255,255,0.10)",
        },
      },
    },
    defaultColorScheme: mode,
    palette: {
      mode,
      primary: { main: accent, contrastText: "#1a1410" },
      secondary: { main: "#6f87b0" },
      background: {
        default: isDark ? "rgba(20,18,24,0.0)" : "rgba(250,248,244,0.0)",
        paper: isDark ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.55)",
      },
      text: {
        primary: textPrimary,
        secondary: textSecondary,
        disabled: isDark ? "rgba(244,241,232,0.38)" : "rgba(36,35,42,0.38)",
      },
      action: {
        active: textPrimary,
        disabled: isDark ? "rgba(244,241,232,0.30)" : "rgba(36,35,42,0.26)",
        hover: isDark ? "rgba(244,241,232,0.08)" : "rgba(36,35,42,0.05)",
        selected: isDark ? "rgba(200,164,101,0.18)" : "rgba(200,164,101,0.12)",
      },
      divider: isDark ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.12)",
    },
    shape: { borderRadius: 14 },
    typography: {
      fontFamily:
        '"Inter","Segoe UI",system-ui,-apple-system,sans-serif',
      h1: { fontWeight: 600, letterSpacing: "-0.02em" },
      h2: { fontWeight: 600, letterSpacing: "-0.02em" },
      h3: { fontWeight: 600, letterSpacing: "-0.01em" },
      button: { textTransform: "none", fontWeight: 500 },
    },
    components: {
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            backdropFilter: "blur(20px) saturate(140%)",
            WebkitBackdropFilter: "blur(20px) saturate(140%)",
            border: `1px solid ${isDark ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.12)"}`,
          },
        },
      },
      MuiAppBar: {
        defaultProps: { elevation: 0, color: "transparent" },
        styleOverrides: {
          root: {
            color: textPrimary,
            backdropFilter: "blur(24px) saturate(140%)",
            WebkitBackdropFilter: "blur(24px) saturate(140%)",
            background: isDark ? "rgba(20,18,24,0.55)" : "rgba(255,255,255,0.55)",
            borderBottom: `1px solid ${isDark ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.12)"}`,
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: { root: { borderRadius: 10 } },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            color: "var(--color-glass-fg)",
            "&.Mui-disabled": {
              color: "color-mix(in oklch, var(--color-glass-muted), transparent 35%)",
            },
          },
        },
      },
      MuiSvgIcon: {
        styleOverrides: {
          root: {
            color: "inherit",
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundImage: "none",
            background: isDark ? "rgba(20,18,24,0.65)" : "rgba(255,255,255,0.55)",
            backdropFilter: "blur(24px) saturate(140%)",
            WebkitBackdropFilter: "blur(24px) saturate(140%)",
          },
        },
      },
    },
  });
}
