"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Divider,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import BackspaceOutlinedIcon from "@mui/icons-material/BackspaceOutlined";
import { COPTIC_LETTERS, SPECIAL_MARKERS } from "@/lib/copticInventory";
import { intentFromKey } from "@/lib/copticKeymap";
import { ChooserPreview } from "@/components/reviewer/ChooserPreview";

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

interface Preview {
  imageUrl: string;
  imageSize: [number, number];
  aabb: [number, number, number, number];
}

interface Props {
  /** Title displayed at the top. */
  title?: string;
  /** Sub-line under the title. */
  subtitle?: string;
  /** Current label value (no diacritics). */
  value: string | null;
  onChange: (next: string | null) => void;
  onSubmit?: () => void;
  onCancel?: () => void;
  /** Hide diacritics + brackets. Defaults to true for cluster mode. */
  hideDiacritics?: boolean;
  /** Hide the "skip" affordance. Skip is enabled by default for new-cluster. */
  allowSkip?: boolean;
  onSkip?: () => void;
  preview?: Preview | null;
  /** Disable submit (e.g. while a mutation is in flight). */
  disabled?: boolean;
  submitLabel?: string;
}

/**
 * A standalone Coptic label picker mirroring the visual layout of the
 * reviewer's `CharChooser`, but with diacritics suppressed and no overline
 * group. Used for cluster label editing and the create-new-cluster flow.
 */
export function CopticPicker({
  title,
  subtitle,
  value,
  onChange,
  onSubmit,
  onCancel,
  hideDiacritics = true,
  allowSkip = false,
  onSkip,
  preview,
  disabled = false,
  submitLabel = "Save",
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [rawMode, setRawMode] = useState(false);

  // Focus input on mount so the Coptic keymap captures keys immediately.
  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, []);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (rawMode) {
      if (e.key === "Enter") {
        e.preventDefault();
        onSubmit?.();
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel?.();
        return;
      }
      if (e.key === "Backspace") {
        e.preventDefault();
        e.stopPropagation();
        onChange(null);
        return;
      }
      if (e.key.length === 1) {
        e.preventDefault();
        e.stopPropagation();
        onChange(e.key);
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
        onChange(intent.label);
        break;
      case "special":
        onChange(intent.token);
        break;
      case "diacritic":
        // ignored in this picker
        break;
      case "control":
        if (intent.action === "commit") onSubmit?.();
        else if (intent.action === "cancel") onCancel?.();
        else if (intent.action === "clear") onChange(null);
        break;
    }
  };

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

  return (
    <Box onKeyDown={onKeyDown} sx={{ p: 2, minWidth: 420, maxWidth: 560 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {title && (
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }} noWrap>
              {title}
            </Typography>
          )}
          {subtitle && (
            <Typography variant="caption" color="text.secondary" noWrap>
              {subtitle}
            </Typography>
          )}
        </Box>
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
        {onCancel && (
          <IconButton size="small" onClick={onCancel} aria-label="close">
            <CloseIcon fontSize="small" />
          </IconButton>
        )}
      </Stack>

      <Stack direction="row" spacing={1} sx={{ my: 1, alignItems: "center" }}>
        <TextField
          inputRef={inputRef}
          value={displayLabel(value)}
          onChange={() => {
            /* read-only proxy */
          }}
          fullWidth
          autoFocus
          size="small"
          placeholder="—"
          sx={{
            flex: 1,
            input: {
              fontFamily: "var(--font-coptic)",
              fontSize: 22,
              textAlign: "center",
            },
          }}
        />
        <IconButton
          size="small"
          onClick={() => onChange(null)}
          aria-label="clear"
          disabled={value == null || value.length === 0}
        >
          <BackspaceOutlinedIcon fontSize="small" />
        </IconButton>
        {preview && (
          <ChooserPreview
            imageUrl={preview.imageUrl}
            imageSize={preview.imageSize}
            aabb={preview.aabb}
          />
        )}
      </Stack>

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
              const isActive = value === l.base;
              return (
                <Button
                  key={l.base}
                  size="small"
                  variant={isActive ? "contained" : "text"}
                  color={isActive ? "primary" : "inherit"}
                  onClick={() => onChange(isActive ? null : l.base)}
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
              const isActive = displayLabel(value) === s.token;
              return (
                <Button
                  key={s.token}
                  size="small"
                  variant={isActive ? "contained" : "outlined"}
                  color={isActive ? "primary" : "inherit"}
                  onClick={() => onChange(isActive ? null : s.token)}
                  title={s.name}
                >
                  {s.display}
                </Button>
              );
            })}
          </Stack>
        </>
      )}

      <Divider sx={{ my: 1 }} />

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        {allowSkip && onSkip && (
          <Button
            size="small"
            variant="text"
            onClick={onSkip}
            disabled={disabled}
          >
            Skip (no label)
          </Button>
        )}
        {onCancel && (
          <Button size="small" variant="text" onClick={onCancel}>
            Cancel
          </Button>
        )}
        {onSubmit && (
          <Button
            size="small"
            variant="contained"
            onClick={onSubmit}
            disabled={disabled}
          >
            {submitLabel}
          </Button>
        )}
      </Stack>
    </Box>
  );
}
