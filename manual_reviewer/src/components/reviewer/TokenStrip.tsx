"use client";
import { useMemo } from "react";
import { Box, Tooltip } from "@mui/material";
import type { ReviewLine, ReviewToken } from "./hooks";
import { useReviewerStore } from "./store";

export interface NewBboxStripItem {
  id: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  label: string | null;
  overline_mark_id?: number | null;
}

interface Props {
  line: ReviewLine;
  onTokenClick: (token: ReviewToken, evt: { clientX: number; clientY: number }) => void;
  newBboxes?: NewBboxStripItem[];
  onNewBboxClick?: (nb: NewBboxStripItem, evt: { clientX: number; clientY: number }) => void;
}

/** Position of a token within its overline group */
type OverlinePos = "solo" | "first" | "middle" | "last" | null;

const GROUP_BLOCKED_ABOVE_CODEPOINTS = new Set([
  "\u0304",
  "\u0305",
  "\u0307",
  "\u0308",
  "\uFE24",
  "\uFE25",
  "\uFE26",
]);

function overlineChar(pos: OverlinePos): string {
  switch (pos) {
    case "solo": return "\u0304";
    case "first": return "\uFE24";
    case "middle": return "\uFE26";
    case "last": return "\uFE25";
    default: return "";
  }
}

function stripGroupBlockedAboveCodepoints(text: string): string {
  return [...text].filter((ch) => !GROUP_BLOCKED_ABOVE_CODEPOINTS.has(ch)).join("");
}

function tokenDisplay(t: ReviewToken, olPos: OverlinePos): string {
  const lbl = t.effective_label;
  if (!lbl) return t.unset ? "" : "·";
  let display: string;
  // Legacy cluster-name tokens (pre-Unicode migration)
  if (lbl.startsWith("_")) {
    switch (lbl) {
      case "_lacuna_dot":
        display = "\u00B7"; break;
      case "_left_square_bracket":
        display = "["; break;
      case "_right_square_bracket":
        display = "]"; break;
      case "_unknown":
        display = "\u2E2C"; break;
      case "_connected_needs_literal_reading":
        display = "\u2248"; break;
      case "_blank":
        display = "\u2423"; break;
      default:
        display = lbl; break;
    }
  } else {
    display = lbl;
  }
  // Group overlines are rendered from overline_mark_id; single overlines stay in the label.
  if (olPos) display = stripGroupBlockedAboveCodepoints(display) + overlineChar(olPos);
  return display;
}

function tokenStateColor(t: ReviewToken): string | undefined {
  if (t.unset) return "rgba(255,99,71,0.35)";
  if (t.user_modified) return "rgba(200,164,101,0.35)";
  if (t.review) return "rgba(255,200,90,0.30)";
  return undefined;
}

type StripItem =
  | { kind: "token"; key: string; x: number; left: number; right: number; overlineMarkId: number | null; token: ReviewToken }
  | { kind: "new"; key: string; x: number; left: number; right: number; overlineMarkId: number | null; nb: NewBboxStripItem };

function tokenBounds(t: ReviewToken): { x: number; left: number; right: number } {
  const q = t.img_quad;
  if (q && q.length > 0) {
    const xs = q.map((p) => p[0]);
    const left = Math.min(...xs);
    const right = Math.max(...xs);
    return { x: xs.reduce((sum, x) => sum + x, 0) / xs.length, left, right };
  }
  const bbox = t.geometry?.warped_bbox;
  if (bbox) return { x: (bbox[0] + bbox[2]) / 2, left: bbox[0], right: bbox[2] };
  return { x: 0, left: 0, right: 0 };
}

function newBboxDisplay(label: string | null, olPos: OverlinePos): string {
  const display = label || "·";
  if (!olPos) return display;
  return stripGroupBlockedAboveCodepoints(display) + overlineChar(olPos);
}

function buildStripItems(tokens: ReviewToken[], newBboxes: NewBboxStripItem[] | undefined): StripItem[] {
  return [
    ...tokens.filter((t) => !t.deleted).map((token) => {
      const bounds = tokenBounds(token);
      return {
        kind: "token" as const,
        key: `t:${token.blob_id}`,
        overlineMarkId: token.overline_mark_id ?? null,
        token,
        ...bounds,
      };
    }),
    ...(newBboxes ?? []).map((nb) => ({
      kind: "new" as const,
      key: `n:${nb.id}`,
      x: (nb.x0 + nb.x1) / 2,
      left: nb.x0,
      right: nb.x1,
      overlineMarkId: nb.overline_mark_id ?? null,
      nb,
    })),
  ].sort((a, b) => a.x - b.x);
}

export function TokenStrip({ line, onTokenClick, newBboxes, onNewBboxClick }: Props) {
  const selectedBlobId = useReviewerStore((s) => s.selectedBlobId);
  const selectedLine = useReviewerStore((s) => s.selectedLine);

  const stripItems = useMemo(() => buildStripItems(line.tokens, newBboxes), [line.tokens, newBboxes]);

  // Compute overline position for each visible item.
  const olPosMap = useMemo(() => {
    const map = new Map<string, OverlinePos>();
    let i = 0;
    while (i < stripItems.length) {
      const mid = stripItems[i].overlineMarkId;
      if (mid != null) {
        let j = i + 1;
        while (j < stripItems.length && stripItems[j].overlineMarkId === mid) j++;
        const groupLen = j - i;
        for (let k = i; k < j; k++) {
          let pos: OverlinePos;
          if (groupLen === 1) pos = "solo";
          else if (k === i) pos = "first";
          else if (k === j - 1) pos = "last";
          else pos = "middle";
          map.set(stripItems[k].key, pos);
        }
        i = j;
      } else {
        i++;
      }
    }
    return map;
  }, [stripItems]);

  // Use the same x-extent as LineCanvas so characters line up horizontally
  // with the bounding boxes drawn on the image strip above.
  const lq = line.line_quad;
  if (!lq) {
    return (
      <Box
        sx={{
          display: "flex",
          gap: 0,
          py: 0.25,
          fontFamily: 'var(--font-coptic), "Noto Sans Coptic", serif',
          fontSize: 16,
          lineHeight: "20px",
          whiteSpace: "nowrap",
        }}
      >
        {line.tokens.map((t) => {
          if (t.deleted) return null;
          return (
          <TokenChar
            key={`${t.line_index}-${t.blob_id}`}
            t={t}
            olPos={olPosMap.get(`t:${t.blob_id}`) ?? null}
            isSelected={
              selectedLine === line.line_index && selectedBlobId === t.blob_id
            }
            onTokenClick={onTokenClick}
          />
          );
        })}
      </Box>
    );
  }

  const xs = lq.map((p) => p[0]);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const span = Math.max(x1 - x0, 1);

  // Compute overline groups: consecutive visible items sharing the same overline_mark_id
  const overlineGroups: { leftPct: number; rightPct: number; markId: number }[] = [];
  {
    let i = 0;
    while (i < stripItems.length) {
      const mid = stripItems[i].overlineMarkId;
      if (mid != null) {
        let j = i + 1;
        while (j < stripItems.length && stripItems[j].overlineMarkId === mid) {
          j++;
        }
        // Only draw group bar when 2+ tokens share the mark
        if (j - i >= 2) {
          const leftPct = ((stripItems[i].left - x0) / span) * 100;
          const rightPct = ((stripItems[j - 1].right - x0) / span) * 100;
          overlineGroups.push({ leftPct, rightPct, markId: mid });
        }
        i = j;
      } else {
        i++;
      }
    }
  }

  return (
    <Box
      sx={{
        position: "relative",
        height: 22,
        width: "100%",
        fontFamily: 'var(--font-coptic), "Noto Sans Coptic", serif',
        fontSize: 15,
        lineHeight: "22px",
      }}
    >
      {/* Overline group borders */}
      {overlineGroups.map((g) => (
        <Box
          key={`ovl-${g.markId}`}
          sx={{
            position: "absolute",
            left: `${g.leftPct}%`,
            width: `${g.rightPct - g.leftPct}%`,
            top: 0,
            height: "100%",
            border: "1.5px solid rgba(60, 130, 220, 0.55)",
            borderRadius: "3px",
            pointerEvents: "none",
          }}
        />
      ))}
      {line.tokens.map((t) => {
        if (t.deleted) return null;
        const q = t.img_quad;
        const cx =
          q && q.length > 0
            ? q.reduce((s, p) => s + p[0], 0) / q.length
            : (x0 + x1) / 2;
        const leftPct = ((cx - x0) / span) * 100;
        const isSelected =
          selectedLine === line.line_index && selectedBlobId === t.blob_id;
        return (
          <Box
            key={`${t.line_index}-${t.blob_id}`}
            sx={{
              position: "absolute",
              left: `${leftPct}%`,
              top: 0,
              transform: "translateX(-50%)",
            }}
          >
            <TokenChar
              t={t}
              olPos={olPosMap.get(`t:${t.blob_id}`) ?? null}
              isSelected={isSelected}
              onTokenClick={onTokenClick}
            />
          </Box>
        );
      })}
      {newBboxes?.map((nb) => {
        const cx = (nb.x0 + nb.x1) / 2;
        const leftPct = ((cx - x0) / span) * 100;
        const isSelected = selectedBlobId === nb.id;
        const olPos = olPosMap.get(`n:${nb.id}`) ?? null;
        const display = newBboxDisplay(nb.label, olPos);
        return (
          <Box
            key={`nb-${nb.id}`}
            sx={{
              position: "absolute",
              left: `${leftPct}%`,
              top: 0,
              transform: "translateX(-50%)",
            }}
          >
            <Tooltip title={`new bbox ${nb.id.slice(0, 8)}`} placement="top" arrow>
              <span
                className="coptic"
                onClick={(e) =>
                  onNewBboxClick?.(nb, { clientX: e.clientX, clientY: e.clientY })
                }
                style={{
                  cursor: "pointer",
                  padding: "0 1px",
                  borderRadius: 2,
                  backgroundColor: "rgba(80,200,120,0.25)",
                  outline: isSelected
                    ? "1.5px solid rgba(80,200,120,0.9)"
                    : undefined,
                  color: nb.label ? "inherit" : "var(--color-text-muted, #999)",
                }}
              >
                {display}
              </span>
            </Tooltip>
          </Box>
        );
      })}
    </Box>
  );
}

interface CharProps {
  t: ReviewToken;
  olPos: OverlinePos;
  isSelected: boolean;
  onTokenClick: (
    token: ReviewToken,
    evt: { clientX: number; clientY: number },
  ) => void;
}

function TokenChar({ t, olPos, isSelected, onTokenClick }: CharProps) {
  const display = tokenDisplay(t, olPos);
  const bg = tokenStateColor(t);
  const isUnset = t.unset && !t.effective_label;
  return (
    <Tooltip
      title={
        <Box sx={{ fontSize: 12, lineHeight: 1.5 }}>
          <div>
            blob {t.blob_id} · cluster {t.cluster}
          </div>
          <div>label: {t.effective_label ?? "—"}</div>
          {t.candidates.length > 0 && (
            <div>candidates: {t.candidates.slice(0, 6).join(" ")}</div>
          )}
        </Box>
      }
      placement="top"
      arrow
    >
      <span
        className="coptic"
        onClick={(e) =>
          onTokenClick(t, { clientX: e.clientX, clientY: e.clientY })
        }
        style={{
          cursor: "pointer",
          padding: "0 1px",
          borderRadius: 2,
          display: isUnset ? "inline-flex" : undefined,
          alignItems: isUnset ? "center" : undefined,
          justifyContent: isUnset ? "center" : undefined,
          minWidth: isUnset ? 10 : undefined,
          height: isUnset ? 16 : undefined,
          verticalAlign: isUnset ? "middle" : undefined,
          border: isUnset ? "1px dashed rgba(255,99,71,0.8)" : undefined,
          backgroundColor: bg,
          outline: isSelected
            ? "1.5px solid var(--color-glass-accent)"
            : undefined,
          color: t.effective_label ? "inherit" : "var(--color-text-muted, #999)",
        }}
      >
        {display}
      </span>
    </Tooltip>
  );
}
