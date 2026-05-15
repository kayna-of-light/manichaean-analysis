"use client";

import * as React from "react";
import { ThemeProvider as MuiThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { buildTheme } from "./theme";

type Mode = "light" | "dark";

type ThemeCtx = {
  mode: Mode;
  toggle: () => void;
  setMode: (m: Mode) => void;
};

const Ctx = React.createContext<ThemeCtx | null>(null);
const STORAGE_KEY = "kmr.theme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = React.useState<Mode>("dark");

  React.useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY) as Mode | null;
    if (stored === "light" || stored === "dark") {
      setModeState(stored);
    } else if (window.matchMedia?.("(prefers-color-scheme: light)").matches) {
      setModeState("light");
    }
  }, []);

  React.useEffect(() => {
    document.documentElement.dataset.theme = mode;
    document.documentElement.style.colorScheme = mode;
  }, [mode]);

  const setMode = React.useCallback((m: Mode) => {
    setModeState(m);
    window.localStorage.setItem(STORAGE_KEY, m);
  }, []);

  const toggle = React.useCallback(() => {
    setModeState((prev) => {
      const next: Mode = prev === "dark" ? "light" : "dark";
      window.localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const theme = React.useMemo(() => buildTheme(mode), [mode]);
  const value = React.useMemo(() => ({ mode, toggle, setMode }), [mode, toggle, setMode]);

  return (
    <Ctx.Provider value={value}>
      <MuiThemeProvider theme={theme} defaultMode={mode}>
        <CssBaseline enableColorScheme />
        {children}
      </MuiThemeProvider>
    </Ctx.Provider>
  );
}

export function useThemeMode() {
  const v = React.useContext(Ctx);
  if (!v) throw new Error("useThemeMode must be used inside ThemeProvider");
  return v;
}
