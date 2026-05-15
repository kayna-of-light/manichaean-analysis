"use client";
import { useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Divider,
  IconButton,
  Popover,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutlined";
import BackspaceOutlinedIcon from "@mui/icons-material/BackspaceOutlined";
import { COPTIC_LETTERS, DIACRITICS, SPECIAL_MARKERS } from "@/lib/copticInventory";
import { intentFromKey, applyDiacritic } from "@/lib/copticKeymap";
import { useReviewerStore } from "./store";
import { useEditMutation } from "./hooks";

const COPTIC_KEYBOARD_LAYOUT: (string | null)[][] = [
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "6"],
  ["a", "s", "S", "d", "f", "F", "g", "h", "H", "j", "k", "l"],
  ["z", "x", "c", "C", "v", "b", "n", "m"],
];

const COPTIC_LETTERS_BY_KEY = new Map(COPTIC_LETTERS.map((letter) => [letter.key, letter]));

type DiacriticSlot = "above" | "below";

const ABOVE_DIACRITICS = new Set(["\u0304", "\u0307", "\u0308"]);
const BELOW_DIACRITICS = new Set(["\u0323"]);

function diacriticSlot(combining: string): DiacriticSlot | null {
  if (ABOVE_DIACRITICS.has(combining)) return "above";
  if (BELOW_DIACRITICS.has(combining)) return "below";
  return null;
}

function slotSet(slot: DiacriticSlot): Set<string> {
  return slot === "above" ? ABOVE_DIACRITICS : BELOW_DIACRITICS;
}

function stripDiacriticSlot(label: string | null | undefined, slot: DiacriticSlot): string | null {
  if (!label) return null;
  const blocked = slotSet(slot);
  const stripped = [...label].filter((ch) => !blocked.has(ch)).join("");
  return stripped || null;
}

function withoutSlotDiacritics(diacritics: string[], slot: DiacriticSlot): string[] {
  const blocked = slotSet(slot);
  return diacritics.filter((mark) => !blocked.has(mark));
}

function toggleExclusiveDiacritic(
  label: string | null | undefined,
  diacritics: string[],
  combining: string,
): { label: string | null; diacritics: string[] } {
  const isActive = label?.includes(combining) ?? false;
  const slot = diacriticSlot(combining);
  if (isActive) {
    const stripped = (label ?? "").split(combining).join("");
    return {
      label: stripped || null,
      diacritics: diacritics.filter((mark) => mark !== combining),
    };
  }
  const base = slot ? stripDiacriticSlot(label, slot) : (label ?? null);
  const nextDiacritics = slot ? withoutSlotDiacritics(diacritics, slot) : diacritics;
  return {
    label: applyDiacritic(base, combining),
    diacritics: [...nextDiacritics, combining],
  };
}

interface Props {
  pageId: string;
  anchorEl: HTMLElement | null;
  onClose: () => void;
}

/** Convert legacy cluster-name labels to their display character */
function displayLabel(lbl: string | null | undefined): string {
  if (!lbl) return "";
  if (!lbl.startsWith("_")) return lbl;
  switch (lbl) {
    case "_lacuna_dot": return "\u00B7";
    case "_left_square_bracket": return "[";
    case "_right_square_bracket": return "]";
    case "_unknown": return "\u2E2C";
    case "_connected_needs_literal_reading": return "\u2248";
    case "_blank": return "\u2423";
    default: return lbl;
  }
}

export function CharChooser({ pageId, anchorEl, onClose }: Props) {
  const anchor = useReviewerStore((s) => s.chooserAnchor);
  const updateLabel = useReviewerStore((s) => s.updateChooserLabel);
  const toggleOverlineLeft = useReviewerStore((s) => s.toggleOverlineLeft);
  const toggleOverlineRight = useReviewerStore((s) => s.toggleOverlineRight);
  const closeChooser = useReviewerStore((s) => s.closeChooser);
  const mutation = useEditMutation(pageId);
  const inputRef = useRef<HTMLInputElement>(null);
  const [, force] = useState(0);
  const [rawMode, setRawMode] = useState(false);

  // Focus input when the popover opens so keymap captures keys.
  useEffect(() => {
    if (anchorEl && inputRef.current) {
      const t = setTimeout(() => inputRef.current?.focus(), 60);
      return () => clearTimeout(t);
    }
  }, [anchorEl]);

  const commit = (deleted = false) => {
    if (!anchor) return;

    const pending = anchor.pendingOverline;
    const isCleared = !deleted && anchor.currentLabel == null;
    const selfId = isCleared
      ? null
      : pending.self !== undefined ? pending.self : anchor.overlineMarkId;
    const label = deleted
      ? null
      : isCleared
        ? ""
        : (selfId != null ? stripDiacriticSlot(anchor.currentLabel, "above") : (anchor.currentLabel ?? null));
    const diacritics = selfId != null
      ? withoutSlotDiacritics(anchor.currentDiacritics, "above")
      : anchor.currentDiacritics;

    const blobEdits: Array<{
      line_index: number;
      blob_id: string | number;
      label?: string | null;
      diacritics?: string[];
      deleted?: boolean;
      overline_mark_id?: number | null;
      source: "manual";
    }> = [];
    const newBboxUpdates: Array<{
      id: string;
      label?: string | null;
      diacritics?: string[];
      overline_mark_id?: number | null;
    }> = [];

    const addOverlineUpdate = (
      target: { blobId: string | number; label?: string | null; isNewBbox?: boolean } | null,
      overlineMarkId: number | null,
    ) => {
      if (!target) return;
      if (target.isNewBbox) {
        newBboxUpdates.push({ id: String(target.blobId), overline_mark_id: overlineMarkId });
      } else {
        blobEdits.push({
          line_index: anchor.lineIndex,
          blob_id: target.blobId,
          label: target.label ?? null,
          overline_mark_id: overlineMarkId,
          source: "manual",
        });
      }
    };

    // For new bboxes: delete removes the bbox; save updates its label
    if (anchor.isNewBbox) {
      if (deleted) {
        mutation.mutate(
          { delete_new_bboxes: [String(anchor.blobId)] },
          { onSuccess: () => closeChooser() },
        );
      } else {
        if (pending.left !== undefined && anchor.leftNeighbor) {
          addOverlineUpdate(anchor.leftNeighbor, pending.left);
        }
        if (pending.right !== undefined && anchor.rightNeighbor) {
          addOverlineUpdate(anchor.rightNeighbor, pending.right);
        }
        mutation.mutate(
          {
            update_new_bboxes: [
              {
                id: String(anchor.blobId),
                label,
                diacritics,
                ...(pending.self !== undefined || isCleared ? { overline_mark_id: selfId } : {}),
              },
              ...newBboxUpdates,
            ],
            ...(blobEdits.length > 0 ? { blob_edits: blobEdits } : {}),
          },
          { onSuccess: () => closeChooser() },
        );
      }
      return;
    }

    blobEdits.push({
      line_index: anchor.lineIndex,
      blob_id: anchor.blobId,
      label,
      diacritics,
      deleted,
      ...(pending.self !== undefined || isCleared ? { overline_mark_id: selfId } : {}),
      source: "manual",
    });

    // Include neighbor overline changes
    if (pending.left !== undefined && anchor.leftNeighbor) {
      addOverlineUpdate(anchor.leftNeighbor, pending.left);
    }
    if (pending.right !== undefined && anchor.rightNeighbor) {
      addOverlineUpdate(anchor.rightNeighbor, pending.right);
    }
    mutation.mutate(
      {
        blob_edits: blobEdits,
        ...(newBboxUpdates.length > 0 ? { update_new_bboxes: newBboxUpdates } : {}),
      },
      { onSuccess: () => closeChooser() },
    );
  };

  const clearLabel = () => {
    updateLabel(null, []);
    force((n) => n + 1);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!anchor) return;

    if (e.key === "Delete") {
      e.preventDefault();
      e.stopPropagation();
      return;
    }

    // Raw mode: type any printable character directly as the label
    if (rawMode) {
      if (e.key === "Enter") { e.preventDefault(); commit(); return; }
      if (e.key === "Escape") { e.preventDefault(); closeChooser(); return; }
      if (e.key === "Backspace") {
        e.preventDefault();
        e.stopPropagation();
        clearLabel();
        return;
      }
      if (e.key.length === 1) {
        e.preventDefault();
        e.stopPropagation();
        updateLabel(e.key, []);
        force((n) => n + 1);
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
        updateLabel(intent.label, []);
        force((n) => n + 1);
        break;
      case "diacritic": {
        const pending = anchor.pendingOverline;
        const selfId = pending.self !== undefined ? pending.self : anchor.overlineMarkId;
        if (selfId != null && diacriticSlot(intent.combining) === "above") break;
        const next = toggleExclusiveDiacritic(
          anchor.currentLabel,
          anchor.currentDiacritics,
          intent.combining,
        );
        updateLabel(next.label, next.diacritics);
        force((n) => n + 1);
        break;
      }
      case "special":
        updateLabel(intent.token, []);
        force((n) => n + 1);
        break;
      case "control":
        if (intent.action === "commit") commit();
        else if (intent.action === "cancel") closeChooser();
        else if (intent.action === "clear") clearLabel();
        else if (intent.action === "candidate" && intent.index !== undefined) {
          const cand = anchor.candidates[intent.index];
          if (cand) {
            updateLabel(cand, []);
            force((n) => n + 1);
          }
        }
        break;
    }
  };

  if (!anchor) return null;

  const pendingOverline = anchor.pendingOverline;
  const effectiveSelfOverlineId = pendingOverline.self !== undefined
    ? pendingOverline.self
    : anchor.overlineMarkId;
  const groupBlocksAbove = effectiveSelfOverlineId != null;
  const currentLabelForDisplay = groupBlocksAbove
    ? stripDiacriticSlot(anchor.currentLabel, "above")
    : anchor.currentLabel;

  const clearAboveForGroup = () => {
    const stripped = stripDiacriticSlot(anchor.currentLabel, "above");
    const diacritics = withoutSlotDiacritics(anchor.currentDiacritics, "above");
    if (stripped !== anchor.currentLabel || diacritics.length !== anchor.currentDiacritics.length) {
      updateLabel(stripped, diacritics);
    }
  };

  return (
    <Popover
      open={Boolean(anchorEl)}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      transformOrigin={{ vertical: "top", horizontal: "center" }}
      slotProps={{ paper: { sx: { p: 2, maxWidth: 520 } } }}
    >
      <Box onKeyDown={onKeyDown}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography variant="caption" color="text.secondary">
            blob {String(anchor.blobId)} · line {anchor.lineIndex}
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button
            size="small"
            variant={rawMode ? "contained" : "outlined"}
            onClick={() => setRawMode((v) => !v)}
            sx={{ minWidth: 0, px: 1, py: 0.25, fontSize: 11, textTransform: "none" }}
          >
            ABC
          </Button>
          <IconButton size="small" onClick={onClose} aria-label="close">
            <CloseIcon fontSize="small" />
          </IconButton>
        </Stack>
        <TextField
          inputRef={inputRef}
          value={displayLabel(currentLabelForDisplay)}
          onChange={() => {/* read-only proxy */}}
          fullWidth
          autoFocus
          size="small"
          sx={{
            my: 1,
            input: {
              fontFamily: "var(--font-coptic)",
              fontSize: 22,
              textAlign: "center",
            },
          }}
        />
        {anchor.candidates.length > 0 && (
          <>
            <Typography variant="caption" color="text.secondary">
              candidates (press 1-9):
            </Typography>
            <Stack direction="row" spacing={0.5} sx={{ my: 0.5, flexWrap: "wrap" }}>
              {anchor.candidates.slice(0, 9).map((c, idx) => (
                <Button
                  key={c + idx}
                  size="small"
                  variant="outlined"
                  onClick={() => updateLabel(c, [])}
                  sx={{ minWidth: 40, fontFamily: "var(--font-coptic)" }}
                >
                  {idx + 1}. {c.startsWith("_") ? c.replace(/^_/, "") : c}
                </Button>
              ))}
            </Stack>
            <Divider sx={{ my: 1 }} />
          </>
        )}
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
            <Stack key={rowIndex} direction="row" spacing={0.5} sx={{ justifyContent: "center" }}>
              {row.map((key, keyIndex) => {
                if (!key) {
                  return <Box key={`spacer-${rowIndex}-${keyIndex}`} sx={{ minWidth: 28, p: 0.5 }} />;
                }
                const l = COPTIC_LETTERS_BY_KEY.get(key);
                if (!l) return null;
                const isActive = anchor.currentLabel?.includes(l.base) ?? false;
                return (
                  <Button
                    key={l.base}
                    size="small"
                    variant={isActive ? "contained" : "text"}
                    color={isActive ? "primary" : "inherit"}
                    onClick={() => {
                      if (isActive) {
                        updateLabel(null, []);
                      } else {
                        updateLabel(l.base, []);
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
        <Typography variant="caption" color="text.secondary">
          Overline group
        </Typography>
        <Stack direction="row" spacing={0} sx={{ my: 0.5, alignItems: "center" }}>
          {(() => {
            const left = anchor.leftNeighbor;
            const right = anchor.rightNeighbor;
            const pending = anchor.pendingOverline;
            // Effective IDs considering pending changes
            const selfId = pending.self !== undefined ? pending.self : anchor.overlineMarkId;
            const leftId = pending.left !== undefined ? pending.left : left?.overlineMarkId ?? null;
            const rightId = pending.right !== undefined ? pending.right : right?.overlineMarkId ?? null;
            const leftConnected = left != null && selfId != null && leftId != null && selfId === leftId;
            const rightConnected = right != null && selfId != null && rightId != null && selfId === rightId;

            // Display: strip combining chars for button readability
            const leftDisplay = displayLabel(left?.label) || "·";
            const rightDisplay = displayLabel(right?.label) || "·";

            return (
              <>
                <Button
                  size="small"
                  variant={leftConnected ? "contained" : "outlined"}
                  color={leftConnected ? "secondary" : "inherit"}
                  disabled={left == null}
                  onClick={() => {
                    if (!leftConnected) clearAboveForGroup();
                    toggleOverlineLeft();
                    force((n) => n + 1);
                  }}
                  sx={{
                    minWidth: 36, fontFamily: "var(--font-coptic)", fontSize: 16,
                    borderTopLeftRadius: 8, borderBottomLeftRadius: 8,
                    borderTopRightRadius: 0, borderBottomRightRadius: 0,
                    borderRight: "none",
                  }}
                  title={left ? `Toggle left: ${leftDisplay}` : "No left neighbor"}
                >
                  {leftDisplay}
                </Button>
                <Button
                  size="small"
                  variant={selfId != null ? "contained" : "outlined"}
                  color={selfId != null ? "primary" : "inherit"}
                  disabled
                  sx={{
                    minWidth: 36, fontFamily: "var(--font-coptic)", fontSize: 16,
                    borderRadius: 0, borderLeft: "none", borderRight: "none",
                  }}
                  title="Single-character overlines are in Diacritics; use the side buttons for grouped overlines"
                >
                  {displayLabel(currentLabelForDisplay) || "?"}
                </Button>
                <Button
                  size="small"
                  variant={rightConnected ? "contained" : "outlined"}
                  color={rightConnected ? "secondary" : "inherit"}
                  disabled={right == null}
                  onClick={() => {
                    if (!rightConnected) clearAboveForGroup();
                    toggleOverlineRight();
                    force((n) => n + 1);
                  }}
                  sx={{
                    minWidth: 36, fontFamily: "var(--font-coptic)", fontSize: 16,
                    borderTopRightRadius: 8, borderBottomRightRadius: 8,
                    borderTopLeftRadius: 0, borderBottomLeftRadius: 0,
                    borderLeft: "none",
                  }}
                  title={right ? `Toggle right: ${rightDisplay}` : "No right neighbor"}
                >
                  {rightDisplay}
                </Button>
              </>
            );
          })()}
        </Stack>
        <Typography variant="caption" color="text.secondary">
          Diacritics
        </Typography>
        <Stack direction="row" spacing={0.5} sx={{ my: 0.5, flexWrap: "wrap" }}>
          {DIACRITICS.map((d) => {
            const isActive = anchor.currentLabel?.includes(d.combining) ?? false;
            const isAbove = diacriticSlot(d.combining) === "above";
            const isDisabled = groupBlocksAbove && isAbove;
            return (
              <Button
                key={d.combining}
                size="small"
                variant={isActive ? "contained" : "outlined"}
                color={isActive ? "primary" : "inherit"}
                disabled={isDisabled}
                onClick={() => {
                  if (isDisabled) return;
                  const next = toggleExclusiveDiacritic(
                    anchor.currentLabel,
                    anchor.currentDiacritics,
                    d.combining,
                  );
                  updateLabel(next.label, next.diacritics);
                }}
                title={isDisabled ? `${d.name} is disabled while this character is in an overline group` : `${d.name} (${d.key})`}
              >
                <span className="coptic">{"\u25CC" + d.combining}</span>
              </Button>
            );
          })}
        </Stack>
        <Typography variant="caption" color="text.secondary">
          Specials
        </Typography>
        <Stack direction="row" spacing={0.5} sx={{ my: 0.5, flexWrap: "wrap" }}>
          {SPECIAL_MARKERS.map((s) => (
            <Button
              key={s.token}
              size="small"
              variant="outlined"
              onClick={() => updateLabel(s.token, [])}
              title={s.name}
            >
              {s.display}
            </Button>
          ))}
        </Stack>
        <Divider sx={{ my: 1 }} />
        <Stack direction="row" spacing={1}>
          <Button
            startIcon={<CheckIcon />}
            variant="contained"
            onClick={() => commit()}
            disabled={mutation.isPending}
          >
            Save (Enter)
          </Button>
          <Button
            startIcon={<BackspaceOutlinedIcon />}
            onClick={clearLabel}
            disabled={mutation.isPending}
          >
            Clear (Backspace)
          </Button>
          <Button
            color="error"
            startIcon={<DeleteOutlineIcon />}
            onClick={() => commit(true)}
            disabled={mutation.isPending}
          >
            Delete
          </Button>
          <Box sx={{ flex: 1 }} />
          <Button onClick={onClose}>Cancel (Esc)</Button>
        </Stack>
      </Box>
    </Popover>
  );
}
