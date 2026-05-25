"use client";

import { useMemo, useRef, useState, useEffect, useCallback } from "react";
import {
  Box,
  Button,
  Divider,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import BackspaceOutlinedIcon from "@mui/icons-material/BackspaceOutlined";
import { COPTIC_LETTERS, DIACRITICS, SPECIAL_MARKERS } from "@/lib/copticInventory";
import { intentFromKey, applyDiacritic } from "@/lib/copticKeymap";

/* --------------------------------------------------------------------------
 * Layout: maps Latin key → position in QWERTY rows. Used for both the
 * CopticPicker (single-char) and MissplitEditor (multi-char).
 * -------------------------------------------------------------------------- */

const COPTIC_KEYBOARD_LAYOUT: (string | null)[][] = [
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "6"],
  ["a", "s", "S", "d", "f", "F", "g", "h", "H", "j", "k", "l"],
  ["z", "x", "c", "C", "v", "b", "n", "m"],
];

const COPTIC_LETTERS_BY_KEY = new Map(
  COPTIC_LETTERS.map((letter) => [letter.key, letter]),
);

function displayLabel(lbl: string | null | undefined): string {
  if (!lbl) return "";
  if (lbl === "\u02D9" || lbl === "\u0387") return "\u00B7";
  if (!lbl.startsWith("_")) return lbl;
  switch (lbl) {
    case "_lacuna_dot":
      return ".";
    case "_middle_dot":
      return "\u00B7";
    case "_unknown":
      return "\u2E2C";
    default:
      return lbl;
  }
}

/* --------------------------------------------------------------------------
 * Modes of operation
 * -------------------------------------------------------------------------- */

export type KeyboardMode = "single" | "multi";

/* --------------------------------------------------------------------------
 * Props
 * -------------------------------------------------------------------------- */

interface BaseProps {
  /** Hide diacritics & brackets. Default true. */
  hideDiacritics?: boolean;
  /** Show the ABC (raw-mode) toggle. Default true. */
  showRawToggle?: boolean;
  /** Optional overline group configuration. If omitted, overline section is hidden. */
  overline?: OverlineConfig;
  /** Called when Enter (commit) is pressed. If omitted, Enter event is not consumed. */
  onCommit?: () => void;
}

/** Overline group state and callbacks for the keyboard. */
export interface OverlineConfig {
  /** Whether this blob has an active overline group */
  selfActive: boolean;
  /** Whether left neighbor is in the same overline group */
  leftConnected: boolean;
  /** Whether right neighbor is in the same overline group */
  rightConnected: boolean;
  /** Display label of left neighbor (or null if none) */
  leftLabel: string | null;
  /** Display label of right neighbor (or null if none) */
  rightLabel: string | null;
  /** Whether a left neighbor exists at all */
  hasLeft: boolean;
  /** Whether a right neighbor exists at all */
  hasRight: boolean;
  /** Display label of the current blob for the center button */
  selfLabel: string | null;
  /** Toggle left connection */
  onToggleLeft: () => void;
  /** Toggle self overline */
  onToggleSelf: () => void;
  /** Toggle right connection */
  onToggleRight: () => void;
}

/**
 * Single-character mode: one char selected at a time (used by CopticPicker).
 */
export interface SingleModeProps extends BaseProps {
  mode: "single";
  /** Currently selected character (null = nothing). */
  value: string | null;
  /** Called when a character is selected or cleared. */
  onChange: (next: string | null) => void;
  /** Active character highlight. */
  activeChar?: string | null;
}

/**
 * Multi-character mode: each button press appends (used by MissplitEditor).
 */
export interface MultiModeProps extends BaseProps {
  mode: "multi";
  /** Current text value. */
  value: string;
  /** Called with the new full string. */
  onChange: (next: string) => void;
  /** Max graphemes allowed (for visual feedback). */
  maxChars?: number;
}

export type CopticKeyboardProps = SingleModeProps | MultiModeProps;

/**
 * Shared Coptic keyboard rendering. Handles the visual layout, key hints,
 * ABC raw mode, specials row, and keyboard event capture.
 *
 * Used by:
 *  - CopticPicker (cluster label editing) in "single" mode
 *  - MissplitEditor (multi-char entry) in "multi" mode
 */
export function CopticKeyboard(props: CopticKeyboardProps) {
  const { hideDiacritics = true, showRawToggle = true, overline, onCommit, mode } = props;
  const inputRef = useRef<HTMLInputElement>(null);
  const [rawMode, setRawMode] = useState(false);

  // Focus input on mount.
  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, []);

  // Refocus when caller changes (e.g. dialog reopened)
  const focus = useCallback(() => {
    setTimeout(() => inputRef.current?.focus(), 30);
  }, []);

  /* ---------------------------------------------------------------------- */
  /* Key handler                                                              */
  /* ---------------------------------------------------------------------- */

  const handleChar = useCallback(
    (ch: string) => {
      if (mode === "single") {
        (props as SingleModeProps).onChange(ch);
      } else {
        const cur = (props as MultiModeProps).value;
        (props as MultiModeProps).onChange(cur + ch);
      }
    },
    [mode, props],
  );

  const handleClear = useCallback(() => {
    if (mode === "single") {
      (props as SingleModeProps).onChange(null);
    } else {
      (props as MultiModeProps).onChange("");
    }
  }, [mode, props]);

  const handleBackspace = useCallback(() => {
    if (mode === "single") {
      (props as SingleModeProps).onChange(null);
    } else {
      const cur = (props as MultiModeProps).value;
      if (cur.length > 0) {
        // Remove last grapheme
        if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
          const segmenter = new Intl.Segmenter(undefined, {
            granularity: "grapheme",
          });
          const segs = [...segmenter.segment(cur)].map((s) => s.segment);
          segs.pop();
          (props as MultiModeProps).onChange(segs.join(""));
        } else {
          (props as MultiModeProps).onChange(cur.slice(0, -1));
        }
      }
    }
  }, [mode, props]);

  const handleDiacritic = useCallback(
    (combining: string) => {
      if (mode === "single") {
        const cur = (props as SingleModeProps).value;
        (props as SingleModeProps).onChange(applyDiacritic(cur, combining));
      } else {
        // Apply diacritic to the last grapheme in the string
        const cur = (props as MultiModeProps).value;
        if (!cur) return;
        if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
          const segmenter = new Intl.Segmenter(undefined, {
            granularity: "grapheme",
          });
          const segs = [...segmenter.segment(cur)].map((s) => s.segment);
          if (segs.length === 0) return;
          const last = segs[segs.length - 1];
          segs[segs.length - 1] = applyDiacritic(last, combining) ?? last;
          (props as MultiModeProps).onChange(segs.join(""));
        } else {
          (props as MultiModeProps).onChange(applyDiacritic(cur, combining) ?? cur);
        }
      }
    },
    [mode, props],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (rawMode) {
      if (e.key === "Backspace") {
        e.preventDefault();
        e.stopPropagation();
        handleBackspace();
        return;
      }
      if (e.key.length === 1) {
        e.preventDefault();
        e.stopPropagation();
        handleChar(e.key);
        return;
      }
      return;
    }

    const intent = intentFromKey(e);
    if (!intent) return;
    e.preventDefault();
    e.stopPropagation();
    switch (intent.kind) {
      case "label":
        handleChar(intent.label);
        break;
      case "special":
        handleChar(intent.token);
        break;
      case "diacritic":
        if (!hideDiacritics) {
          handleDiacritic(intent.combining);
        }
        break;
      case "control":
        if (intent.action === "commit" && onCommit) { onCommit(); }
        else if (intent.action === "clear") handleClear();
        break;
    }
  };

  /* ---------------------------------------------------------------------- */
  /* Specials list                                                            */
  /* ---------------------------------------------------------------------- */

  const specials = useMemo(
    () =>
      hideDiacritics
        ? SPECIAL_MARKERS.filter(
            (s) =>
              !["[", "]", "(", ")"].includes(s.token) &&
              !s.token.startsWith("_left_") &&
              !s.token.startsWith("_right_"),
          )
        : SPECIAL_MARKERS,
    [hideDiacritics],
  );

  /* ---------------------------------------------------------------------- */
  /* Display value                                                            */
  /* ---------------------------------------------------------------------- */

  const displayValue =
    mode === "single"
      ? displayLabel((props as SingleModeProps).value)
      : (props as MultiModeProps).value;

  const activeChar =
    mode === "single" ? (props as SingleModeProps).value : null;

  /* ---------------------------------------------------------------------- */
  /* Render                                                                   */
  /* ---------------------------------------------------------------------- */

  return (
    <Box onKeyDown={onKeyDown} tabIndex={-1}>
      {/* Input row */}
      <Stack direction="row" spacing={1} sx={{ mb: 1, alignItems: "center" }}>
        <TextField
          inputRef={inputRef}
          value={displayValue}
          onChange={(e) => {
            // In multi mode, allow direct typing into the field
            if (mode === "multi") {
              (props as MultiModeProps).onChange(e.target.value);
            }
          }}
          fullWidth
          size="small"
          placeholder={mode === "single" ? "—" : "Type characters…"}
          slotProps={{
            input: {
              readOnly: mode === "single",
              sx: {
                fontFamily: "var(--font-coptic)",
                fontSize: mode === "multi" ? 18 : 22,
                textAlign: mode === "single" ? "center" : "left",
                letterSpacing: mode === "multi" ? 3 : undefined,
              },
            },
          }}
          sx={{ flex: 1 }}
        />
        <IconButton
          size="small"
          onClick={handleBackspace}
          aria-label="backspace"
          disabled={
            mode === "single"
              ? ((props as SingleModeProps).value ?? "").length === 0
              : (props as MultiModeProps).value.length === 0
          }
        >
          <BackspaceOutlinedIcon fontSize="small" />
        </IconButton>
        {showRawToggle && (
          <Button
            size="small"
            variant={rawMode ? "contained" : "outlined"}
            onClick={() => setRawMode((v) => !v)}
            sx={{
              minWidth: 0,
              px: 1,
              py: 0.25,
              fontSize: 11,
              textTransform: "none",
            }}
          >
            ABC
          </Button>
        )}
      </Stack>

      {/* Coptic letters grid */}
      <Typography variant="caption" color="text.secondary">
        Coptic letters
      </Typography>
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0.5,
          my: 0.5,
        }}
      >
        {COPTIC_KEYBOARD_LAYOUT.map((row, rowIndex) => (
          <Stack
            key={rowIndex}
            direction="row"
            spacing={0.5}
            sx={{ justifyContent: "center" }}
          >
            {row.map((key, keyIndex) => {
              if (!key) {
                return (
                  <Box
                    key={`spacer-${rowIndex}-${keyIndex}`}
                    sx={{ minWidth: 28, p: 0.5 }}
                  />
                );
              }
              const l = COPTIC_LETTERS_BY_KEY.get(key);
              if (!l) return null;
              const isActive = mode === "single" && activeChar === l.base;
              return (
                <Button
                  key={l.base}
                  size="small"
                  variant={isActive ? "contained" : "text"}
                  color={isActive ? "primary" : "inherit"}
                  onClick={() => {
                    if (mode === "single") {
                      const singleProps = props as SingleModeProps;
                      singleProps.onChange(isActive ? null : l.base);
                    } else {
                      handleChar(l.base);
                    }
                  }}
                  sx={{
                    position: "relative",
                    fontFamily: "var(--font-coptic)",
                    fontSize: 18,
                    minWidth: 28,
                    p: 0.5,
                  }}
                  title={`${l.name} (${l.key})`}
                >
                  {l.base}
                  <Box
                    component="sup"
                    aria-hidden="true"
                    sx={{
                      position: "absolute",
                      top: 1,
                      right: 3,
                      fontFamily: "var(--font-sans)",
                      fontSize: 8,
                      fontWeight: 600,
                      lineHeight: 1,
                      color: "text.disabled",
                      pointerEvents: "none",
                    }}
                  >
                    {l.key}
                  </Box>
                </Button>
              );
            })}
          </Stack>
        ))}
      </Box>

      {/* Overline group */}
      {overline && (
        <>
          <Typography variant="caption" color="text.secondary">
            Overline group
          </Typography>
          <Stack direction="row" spacing={0} sx={{ my: 0.5, alignItems: "center" }}>
            <Button
              size="small"
              variant={overline.leftConnected ? "contained" : "outlined"}
              color={overline.leftConnected ? "secondary" : "inherit"}
              disabled={!overline.hasLeft}
              onClick={overline.onToggleLeft}
              sx={{
                minWidth: 36,
                fontFamily: "var(--font-coptic)",
                fontSize: 16,
                borderTopLeftRadius: 8,
                borderBottomLeftRadius: 8,
                borderTopRightRadius: 0,
                borderBottomRightRadius: 0,
                borderRight: "none",
              }}
              title={overline.hasLeft ? `Toggle left: ${overline.leftLabel || "·"}` : "No left neighbor"}
            >
              {overline.leftLabel || "·"}
            </Button>
            <Button
              size="small"
              variant={overline.selfActive ? "contained" : "outlined"}
              color={overline.selfActive ? "primary" : "inherit"}
              disabled={!overline.selfActive}
              onClick={overline.onToggleSelf}
              sx={{
                minWidth: 36,
                fontFamily: "var(--font-coptic)",
                fontSize: 16,
                borderRadius: 0,
                borderLeft: "none",
                borderRight: "none",
              }}
              title={overline.selfActive
                ? "Clear group overline from this character"
                : "Use the side buttons to start a grouped overline"}
            >
              {overline.selfLabel || "?"}
            </Button>
            <Button
              size="small"
              variant={overline.rightConnected ? "contained" : "outlined"}
              color={overline.rightConnected ? "secondary" : "inherit"}
              disabled={!overline.hasRight}
              onClick={overline.onToggleRight}
              sx={{
                minWidth: 36,
                fontFamily: "var(--font-coptic)",
                fontSize: 16,
                borderTopRightRadius: 8,
                borderBottomRightRadius: 8,
                borderTopLeftRadius: 0,
                borderBottomLeftRadius: 0,
                borderLeft: "none",
              }}
              title={overline.hasRight ? `Toggle right: ${overline.rightLabel || "·"}` : "No right neighbor"}
            >
              {overline.rightLabel || "·"}
            </Button>
          </Stack>
        </>
      )}

      {/* Diacritics row */}
      {!hideDiacritics && (
        <>
          <Typography variant="caption" color="text.secondary">
            Diacritics
          </Typography>
          <Stack
            direction="row"
            spacing={0.5}
            sx={{ my: 0.5, flexWrap: "wrap" }}
          >
            {DIACRITICS.map((d) => (
              <Button
                key={d.combining}
                size="small"
                variant="outlined"
                color="inherit"
                onClick={() => handleDiacritic(d.combining)}
                title={`${d.name} (${d.key})`}
              >
                <span style={{ fontFamily: "var(--font-coptic)" }}>
                  {"\u25CC" + d.combining}
                </span>
              </Button>
            ))}
          </Stack>
        </>
      )}

      {/* Specials row */}
      {specials.length > 0 && (
        <>
          <Typography variant="caption" color="text.secondary">
            Specials
          </Typography>
          <Stack
            direction="row"
            spacing={0.5}
            sx={{ my: 0.5, flexWrap: "wrap" }}
          >
            {specials.map((s) => {
              const isActive =
                mode === "single" &&
                displayLabel((props as SingleModeProps).value) === s.token;
              return (
                <Button
                  key={s.token}
                  size="small"
                  variant={isActive ? "contained" : "outlined"}
                  color={isActive ? "primary" : "inherit"}
                  onClick={() => {
                    if (mode === "single") {
                      const singleProps = props as SingleModeProps;
                      singleProps.onChange(isActive ? null : s.token);
                    } else {
                      handleChar(s.token);
                    }
                  }}
                  title={s.name}
                >
                  {s.display}
                </Button>
              );
            })}
          </Stack>
        </>
      )}
    </Box>
  );
}

/** Expose focus method for parent components that need to refocus after actions. */
CopticKeyboard.displayName = "CopticKeyboard";
