"use client";
import { useMemo } from "react";
import { Box } from "@mui/material";
import type { ReviewLine, ReviewToken, TokenWarningEntry } from "./hooks";
import { useReviewerStore } from "./store";

export type WarningMap = Map<string, TokenWarningEntry>;

/** Build lookup key for warning map */
function warningKey(lineIndex: number, blobId: number | string): string {
  return `${lineIndex}:${blobId}`;
}

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
  warnings?: WarningMap;
}

/** Position of a token within its overline group */
type OverlinePos = "solo" | "first" | "middle" | "last" | null;

const OVERLINE_CODEPOINTS = new Set([
  "\u0304",
  "\u0305",
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

function stripOverlineCodepoints(text: string): string {
  return [...text].filter((ch) => !OVERLINE_CODEPOINTS.has(ch)).join("");
}

function tokenDisplay(t: ReviewToken, olPos: OverlinePos): string {
  const lbl = t.effective_label;
  if (!lbl) return t.unset ? "" : "·";
  let display: string;
  // Legacy cluster-name tokens (pre-Unicode migration)
  if (lbl.startsWith("_")) {
    switch (lbl) {
      case "_lacuna_dot":
        display = "."; break;
      case "_middle_dot":
        display = "\u00B7"; break;
      case "_left_square_bracket":
        display = "["; break;
      case "_right_square_bracket":
        display = "]"; break;
      case "_left_parenthesis":
      case "_left_paren":
        display = "("; break;
      case "_right_parenthesis":
      case "_right_paren":
        display = ")"; break;
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
    display = lbl === "\u02D9" || lbl === "\u0387" ? "\u00B7" : lbl;
  }
  // Group overlines are rendered from overline_mark_id; single overlines stay in the label.
  if (olPos) display = stripOverlineCodepoints(display) + overlineChar(olPos);
  return display;
}

function tokenStateColor(t: ReviewToken): string | undefined {
  if (t.unset) return "rgba(255,99,71,0.35)";
  if (t.editorial_overlay) return "rgba(185,95,0,0.22)";
  if (t.user_modified) return "rgba(200,164,101,0.35)";
  if (t.review) return "rgba(255,200,90,0.30)";
  return undefined;
}

type StripItem =
  | { kind: "token"; key: string; x: number; left: number; right: number; overlineMarkId: number | null; v1Line: number; token: ReviewToken }
  | { kind: "new"; key: string; x: number; left: number; right: number; overlineMarkId: number | null; v1Line: number; nb: NewBboxStripItem };

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

function tokenEditId(token: ReviewToken): string {
  return token.edit_id ?? String(token.blob_id);
}

function newBboxDisplay(label: string | null, olPos: OverlinePos): string {
  const display = label || "·";
  if (!olPos) return display;
  return stripOverlineCodepoints(display) + overlineChar(olPos);
}

function tokenTitle(t: ReviewToken): string {
  const lines = [
    `blob ${t.blob_id} · cluster ${t.cluster}`,
    `label: ${t.effective_label ?? "—"}`,
  ];
  if (t.edit_id && t.edit_id !== String(t.blob_id)) lines.splice(1, 0, `edit id: ${t.edit_id}`);
  if (t.editorial_overlay) lines.push(`editorial: ${t.editorial_overlay.sentence_text}`);
  if (t.candidates.length > 0) lines.push(`candidates: ${t.candidates.slice(0, 6).join(" ")}`);
  return lines.join("\n");
}

function buildStripItems(tokens: ReviewToken[], newBboxes: NewBboxStripItem[] | undefined): StripItem[] {
  // Compute sorted visible tokens to determine v1Line for new_bboxes
  const visibleTokens = tokens.filter((t) => !t.deleted);
  const tokenItems = visibleTokens.map((token) => {
    const bounds = tokenBounds(token);
    return {
      kind: "token" as const,
      key: `t:${token.line_index}:${token.v1_line_index ?? 0}:${tokenEditId(token)}`,
      overlineMarkId: token.overline_mark_id ?? null,
      v1Line: token.v1_line_index ?? 0,
      token,
      ...bounds,
    };
  });

  // For new_bboxes, determine v1Line from nearest token by x position
  const nbItems = (newBboxes ?? []).map((nb) => {
    const cx = (nb.x0 + nb.x1) / 2;
    let bestV1Line = 0;
    let bestDist = Infinity;
    for (const ti of tokenItems) {
      const d = Math.abs(ti.x - cx);
      if (d < bestDist) { bestDist = d; bestV1Line = ti.v1Line; }
    }
    return {
      kind: "new" as const,
      key: `n:${nb.id}`,
      x: cx,
      left: nb.x0,
      right: nb.x1,
      overlineMarkId: nb.overline_mark_id ?? null,
      v1Line: bestV1Line,
      nb,
    };
  });

  return [...tokenItems, ...nbItems].sort((a, b) => a.v1Line !== b.v1Line ? a.v1Line - b.v1Line : a.x - b.x);
}

/** Characters that should not receive an overline combining mark, even if
 *  they are part of an overline group. They remain visually "inside" the group
 *  but the macron skips over them. */
const OVERLINE_SKIP_LABELS = new Set([
  "[", "]", "(", ")", ".", "\u00B7",
  "_left_square_bracket", "_right_square_bracket",
  "_left_parenthesis", "_right_parenthesis", "_left_paren", "_right_paren",
  "_lacuna_dot", "_middle_dot",
]);

function isOverlineSkip(item: StripItem): boolean {
  const lbl = item.kind === "token"
    ? item.token.effective_label
    : item.nb.label;
  return lbl != null && OVERLINE_SKIP_LABELS.has(lbl);
}

export function TokenStrip({ line, onTokenClick, newBboxes, onNewBboxClick, warnings }: Props) {
  const selectedBlobId = useReviewerStore((s) => s.selectedBlobId);
  const selectedLine = useReviewerStore((s) => s.selectedLine);

  const stripItems = useMemo(() => buildStripItems(line.tokens, newBboxes), [line.tokens, newBboxes]);

  // Compute overline position for each visible item.
  // Brackets/dots inside an overline group are skipped — they stay in the group
  // but don't receive the combining macron character.
  const olPosMap = useMemo(() => {
    const map = new Map<string, OverlinePos>();
    let i = 0;
    while (i < stripItems.length) {
      const mid = stripItems[i].overlineMarkId;
      if (mid != null) {
        let j = i + 1;
        while (j < stripItems.length && stripItems[j].overlineMarkId === mid) j++;
        // Collect non-skip indices within this overline group
        const letterIndices: number[] = [];
        for (let k = i; k < j; k++) {
          if (!isOverlineSkip(stripItems[k])) letterIndices.push(k);
        }
        // Assign positions only to non-skip items
        for (let li = 0; li < letterIndices.length; li++) {
          const k = letterIndices[li];
          let pos: OverlinePos;
          if (letterIndices.length === 1) pos = "solo";
          else if (li === 0) pos = "first";
          else if (li === letterIndices.length - 1) pos = "last";
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
        {stripItems.map((item) => {
          const wKey = item.kind === "token"
            ? warningKey(item.token.line_index, item.token.blob_id)
            : warningKey(line.line_index, `nb:${item.nb.id}`);
          return (
            <StripItemChar
              key={item.key}
              item={item}
              olPos={olPosMap.get(item.key) ?? null}
              selectedLine={selectedLine}
              selectedBlobId={selectedBlobId}
              onTokenClick={onTokenClick}
              onNewBboxClick={onNewBboxClick}
              warningLevel={wKey ? warnings?.get(wKey)?.level : undefined}
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
      {stripItems.map((item) => {
        const cx =
          item.kind === "token" && item.token.img_quad && item.token.img_quad.length > 0
            ? item.token.img_quad.reduce((s, p) => s + p[0], 0) / item.token.img_quad.length
            : item.x;
        const leftPct = ((cx - x0) / span) * 100;
        return (
          <Box
            key={item.key}
            sx={{
              position: "absolute",
              left: `${leftPct}%`,
              top: 0,
              transform: "translateX(-50%)",
            }}
          >
            <StripItemChar
              item={item}
              olPos={olPosMap.get(item.key) ?? null}
              selectedLine={selectedLine}
              selectedBlobId={selectedBlobId}
              onTokenClick={onTokenClick}
              onNewBboxClick={onNewBboxClick}
              warningLevel={warnings?.get(
                item.kind === "token"
                  ? warningKey(item.token.line_index, item.token.blob_id)
                  : warningKey(line.line_index, `nb:${item.nb.id}`)
              )?.level}
            />
          </Box>
        );
      })}
    </Box>
  );
}

interface StripItemCharProps {
  item: StripItem;
  olPos: OverlinePos;
  selectedLine: number | null;
  selectedBlobId: number | string | null;
  onTokenClick: (token: ReviewToken, evt: { clientX: number; clientY: number }) => void;
  onNewBboxClick?: (nb: NewBboxStripItem, evt: { clientX: number; clientY: number }) => void;
  warningLevel?: "warn" | "alert";
}

function StripItemChar({
  item,
  olPos,
  selectedLine,
  selectedBlobId,
  onTokenClick,
  onNewBboxClick,
  warningLevel,
}: StripItemCharProps) {
  if (item.kind === "token") {
    return (
      <TokenChar
        t={item.token}
        olPos={olPos}
        isSelected={selectedLine === item.token.line_index && String(selectedBlobId) === tokenEditId(item.token)}
        onTokenClick={onTokenClick}
        warningLevel={warningLevel}
      />
    );
  }

  const display = newBboxDisplay(item.nb.label, olPos);
  const isSelected = selectedBlobId === item.nb.id;
  return (
    <span
      className="coptic"
      title={`new bbox ${item.nb.id.slice(0, 8)}`}
      onClick={(e) => onNewBboxClick?.(item.nb, { clientX: e.clientX, clientY: e.clientY })}
      style={{
        cursor: "pointer",
        padding: "0 1px",
        borderRadius: 2,
        backgroundColor: "rgba(80,200,120,0.25)",
        outline: isSelected ? "1.5px solid rgba(80,200,120,0.9)" : undefined,
        color: item.nb.label ? "inherit" : "var(--color-text-muted, #999)",
      }}
    >
      {display}
    </span>
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
  warningLevel?: "warn" | "alert";
}

function TokenChar({ t, olPos, isSelected, onTokenClick, warningLevel }: CharProps) {
  const display = tokenDisplay(t, olPos);
  const bg = tokenStateColor(t);
  const isUnset = t.unset && !t.effective_label;
  return (
    <span
      className="coptic"
      title={tokenTitle(t)}
      onClick={(e) =>
        onTokenClick(t, { clientX: e.clientX, clientY: e.clientY })
      }
      style={{
        cursor: "pointer",
        padding: "0 1px",
        borderRadius: 2,
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: isUnset ? "center" : undefined,
        minWidth: isUnset ? 10 : undefined,
        verticalAlign: "top",
        border: isUnset ? "1px dashed rgba(255,99,71,0.8)" : undefined,
        backgroundColor: bg,
        outline: isSelected
          ? "1.5px solid var(--color-glass-accent)"
          : undefined,
        color: t.effective_label ? "inherit" : "var(--color-text-muted, #999)",
      }}
    >
      <span style={{ lineHeight: "20px" }}>{display}</span>
      {warningLevel && (
        <span
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            backgroundColor: warningLevel === "alert" ? "#ff5252" : "#ffc107",
            marginTop: 1,
            flexShrink: 0,
          }}
        />
      )}
    </span>
  );
}
