/**
 * bigramScorer.ts
 *
 * Scores tokens on a page against the bigram model built from reviewed pages.
 * Returns per-token warning levels: "ok" | "warn" | "alert"
 */

import { readFileSync, existsSync } from "fs";
import path from "path";

export type WarningLevel = "ok" | "warn" | "alert";

export interface TokenWarning {
  lineIndex: number;
  blobId: number | string;
  level: WarningLevel;
  reasons: string[];
}

interface BigramModel {
  version: number;
  stats: {
    totalChars: number;
    totalBigrams: number;
    uniqueChars: number;
    uniqueBigrams: number;
  };
  charCounts: Record<string, number>;
  bigramCounts: Record<string, number>;
  confusionPairs: Record<string, number>;
  confusionChars: string[];
  deletionProfile: {
    count: number;
    areaThreshold: number;
    keptMinArea: number;
    medianArea: number;
    medianAspect: number;
  };
  lineStartCounts?: Record<string, number>;
  lineEndCounts?: Record<string, number>;
}

let cachedModel: BigramModel | null = null;

function loadModel(): BigramModel | null {
  if (cachedModel) return cachedModel;
  const modelPath = path.join(process.cwd(), "data", "bigram_model.json");
  if (!existsSync(modelPath)) return null;
  cachedModel = JSON.parse(readFileSync(modelPath, "utf8"));
  return cachedModel;
}

/** Invalidate cached model (call after rebuilding) */
export function invalidateModel(): void {
  cachedModel = null;
}

/**
 * Incrementally update the in-memory model when an edit changes a label.
 * This keeps the model live without needing a full rebuild.
 *
 * Cases:
 * - Label correction (old→new): decrement old bigrams, increment new bigrams, record confusion
 * - Deletion (old→null): decrement old bigrams, ADD bridging bigram left|right (neighbors now adjacent)
 * - Insertion (null→new): increment new bigrams, REMOVE bridging bigram left|right if it existed
 *
 * @param leftLabel - The non-placeholder char to the left (null if none)
 * @param oldLabel - The previous label at this position (null if new insertion)
 * @param newLabel - The new label at this position (null if deletion)
 * @param rightLabel - The non-placeholder char to the right (null if none)
 */
export function applyEditToModel(
  leftLabel: string | null,
  oldLabel: string | null,
  newLabel: string | null,
  rightLabel: string | null,
): void {
  const model = loadModel();
  if (!model) return;

  // --- Decrement old counts ---
  if (oldLabel) {
    if (model.charCounts[oldLabel]) {
      model.charCounts[oldLabel]--;
      if (model.charCounts[oldLabel] <= 0) delete model.charCounts[oldLabel];
    }
    if (leftLabel) {
      const bg = `${leftLabel}|${oldLabel}`;
      if (model.bigramCounts[bg]) {
        model.bigramCounts[bg]--;
        if (model.bigramCounts[bg] <= 0) delete model.bigramCounts[bg];
      }
    }
    if (rightLabel) {
      const bg = `${oldLabel}|${rightLabel}`;
      if (model.bigramCounts[bg]) {
        model.bigramCounts[bg]--;
        if (model.bigramCounts[bg] <= 0) delete model.bigramCounts[bg];
      }
    }
  }

  // --- Increment new counts ---
  if (newLabel) {
    model.charCounts[newLabel] = (model.charCounts[newLabel] ?? 0) + 1;
    if (leftLabel) {
      const bg = `${leftLabel}|${newLabel}`;
      model.bigramCounts[bg] = (model.bigramCounts[bg] ?? 0) + 1;
    }
    if (rightLabel) {
      const bg = `${newLabel}|${rightLabel}`;
      model.bigramCounts[bg] = (model.bigramCounts[bg] ?? 0) + 1;
    }
  }

  // --- Handle bridging bigram (left|right) for DELETIONS only ---
  // When a char is deleted, left and right become adjacent → reinforce that pair.
  // We do NOT decrement the bridge on insertion — inserting a missed char on one
  // page doesn't invalidate the left|right pair being valid on other pages.
  if (leftLabel && rightLabel && oldLabel && !newLabel) {
    const bridge = `${leftLabel}|${rightLabel}`;
    model.bigramCounts[bridge] = (model.bigramCounts[bridge] ?? 0) + 1;
  }

  // --- Track confusion pair (old→new correction) ---
  if (oldLabel && newLabel && oldLabel !== newLabel) {
    const pair = `${oldLabel}→${newLabel}`;
    model.confusionPairs[pair] = (model.confusionPairs[pair] ?? 0) + 1;
    // Ensure both chars are in the confusion set
    if (!model.confusionChars.includes(oldLabel)) model.confusionChars.push(oldLabel);
    if (!model.confusionChars.includes(newLabel)) model.confusionChars.push(newLabel);
  }

  // --- Update line-start/end position counts ---
  if (model.lineStartCounts) {
    // If this is the first char on the line (no left neighbor)
    if (leftLabel === null) {
      // Decrement old line-start count
      if (oldLabel && model.lineStartCounts[oldLabel]) {
        model.lineStartCounts[oldLabel]--;
        if (model.lineStartCounts[oldLabel] <= 0) delete model.lineStartCounts[oldLabel];
      }
      // Increment new line-start count
      if (newLabel) {
        model.lineStartCounts[newLabel] = (model.lineStartCounts[newLabel] ?? 0) + 1;
      }
      // If we deleted the first char, rightLabel is now the line-starter
      if (oldLabel && !newLabel && rightLabel) {
        model.lineStartCounts[rightLabel] = (model.lineStartCounts[rightLabel] ?? 0) + 1;
      }
      // If we inserted before the old first char, rightLabel loses its start status
      if (!oldLabel && newLabel && rightLabel && model.lineStartCounts[rightLabel]) {
        model.lineStartCounts[rightLabel]--;
        if (model.lineStartCounts[rightLabel] <= 0) delete model.lineStartCounts[rightLabel];
      }
    }
  }
  if (model.lineEndCounts) {
    // If this is the last char on the line (no right neighbor)
    if (rightLabel === null) {
      if (oldLabel && model.lineEndCounts[oldLabel]) {
        model.lineEndCounts[oldLabel]--;
        if (model.lineEndCounts[oldLabel] <= 0) delete model.lineEndCounts[oldLabel];
      }
      if (newLabel) {
        model.lineEndCounts[newLabel] = (model.lineEndCounts[newLabel] ?? 0) + 1;
      }
      if (oldLabel && !newLabel && leftLabel) {
        model.lineEndCounts[leftLabel] = (model.lineEndCounts[leftLabel] ?? 0) + 1;
      }
      // If we inserted after the old last char, leftLabel loses its end status
      if (!oldLabel && newLabel && leftLabel && model.lineEndCounts[leftLabel]) {
        model.lineEndCounts[leftLabel]--;
        if (model.lineEndCounts[leftLabel] <= 0) delete model.lineEndCounts[leftLabel];
      }
    }
  }
}

/**
 * Reinforce a confirmed-correct line into the model.
 * Called when a line is marked "done" or "special" — the user has verified
 * all tokens are correct. Increments char and bigram counts by +1 each,
 * which gradually reduces false positives without making the model permissive.
 *
 * Does NOT remove confusion chars or alter confusion pairs — those are
 * permanent signals from actual corrections.
 *
 * @param labels - The effective labels on the line (nulls for deleted/missing)
 */
export function reinforceConfirmedLine(labels: (string | null)[]): void {
  const model = loadModel();
  if (!model) return;

  const PLACEHOLDER = new Set(["E", "?"]);

  // Collect non-placeholder, non-null labels in order
  const confirmed: string[] = [];
  for (const l of labels) {
    if (l && !PLACEHOLDER.has(l)) confirmed.push(l);
  }

  // Increment char counts (+1 each)
  for (const ch of confirmed) {
    model.charCounts[ch] = (model.charCounts[ch] ?? 0) + 1;
  }

  // Increment bigram counts (+1 each adjacent pair)
  for (let i = 0; i < confirmed.length - 1; i++) {
    const bg = `${confirmed[i]}|${confirmed[i + 1]}`;
    model.bigramCounts[bg] = (model.bigramCounts[bg] ?? 0) + 1;
  }

  // Reinforce line-start/end position (+1 each)
  if (confirmed.length > 0) {
    if (!model.lineStartCounts) model.lineStartCounts = {};
    if (!model.lineEndCounts) model.lineEndCounts = {};
    model.lineStartCounts[confirmed[0]] = (model.lineStartCounts[confirmed[0]] ?? 0) + 1;
    model.lineEndCounts[confirmed[confirmed.length - 1]] = (model.lineEndCounts[confirmed[confirmed.length - 1]] ?? 0) + 1;
  }
}

interface TokenInput {
  blob_id: number;
  line_index: number;
  label: string | null;
  effective_label: string | null;
  deleted: boolean;
  geometry?: {
    warped_bbox?: [number, number, number, number];
  } | null;
}

/**
 * Score all tokens on a page, returning warnings for each suspicious token.
 * Only returns entries with level !== "ok" to keep payloads small.
 *
 * Scoring philosophy (AGGRESSIVE — optimized for recall):
 * - Placeholders (E, ?) are unresolved readings → always ALERT
 * - All other chars scored on multiple signals, stacked additively
 * - Confusion char bonus is unconditional (+1 just for being in the list)
 * - Unpaired brackets get a penalty (may indicate misidentified glyph)
 * - Bigrams skip over placeholders (E/?) only — brackets participate fully
 * - False positives are acceptable; false negatives are not
 */

/** Chars that represent unresolved/uncertain readings — always need attention */
const PLACEHOLDER_CHARS = new Set(["E", "?"]);

export function scorePageTokens(
  lines: { line_index: number; tokens: TokenInput[] }[],
): TokenWarning[] {
  const model = loadModel();
  if (!model) return [];

  const confusionSet = new Set(model.confusionChars);

  // Build diacritic family map: base char → [variant labels with higher codepoint count]
  // e.g. "ⲓ" → ["ⲓ̈", "ⲓ̣", "ⲓ̄", ...]
  const diacriticVariants: Map<string, string[]> = new Map();
  for (const ch of Object.keys(model.charCounts)) {
    const codepoints = [...ch];
    if (codepoints.length > 1) {
      const base = codepoints[0];
      // Only map if the base char also exists in the model
      if (model.charCounts[base]) {
        if (!diacriticVariants.has(base)) diacriticVariants.set(base, []);
        diacriticVariants.get(base)!.push(ch);
      }
    }
  }

  const warnings: TokenWarning[] = [];

  for (const line of lines) {
    // Get effective labels for this line (skip deleted)
    const activeTokens = line.tokens.filter((t) => !t.deleted);
    const labels = activeTokens.map((t) => t.effective_label ?? t.label);

    // Pre-compute bracket pairing for this line
    const bracketPaired = computeBracketPairing(labels);

    // Build text indices: all chars except placeholders (E/?)
    // Placeholders get scored separately; they're excluded from bigram context
    const textIndices: number[] = [];
    for (let i = 0; i < activeTokens.length; i++) {
      const lbl = labels[i];
      if (lbl && !PLACEHOLDER_CHARS.has(lbl)) {
        textIndices.push(i);
      }
    }

    // Score placeholders first — always ALERT
    for (let i = 0; i < activeTokens.length; i++) {
      const lbl = labels[i];
      if (lbl && PLACEHOLDER_CHARS.has(lbl)) {
        warnings.push({
          lineIndex: line.line_index,
          blobId: activeTokens[i].blob_id,
          level: "alert",
          reasons: [`unresolved placeholder: ${lbl}`],
        });
      }
    }

    // Score all other characters
    for (let ti = 0; ti < textIndices.length; ti++) {
      const i = textIndices[ti];
      const tok = activeTokens[i];
      const label = labels[i]!;

      const reasons: string[] = [];
      let score = 0;

      // ─── Signal 1: Bigram anomaly ──────────────────────────────────────
      // Form bigrams with adjacent non-placeholder chars
      const leftLabel = ti > 0 ? labels[textIndices[ti - 1]] : null;
      const rightLabel = ti < textIndices.length - 1 ? labels[textIndices[ti + 1]] : null;

      if (leftLabel) {
        const leftBg = `${leftLabel}|${label}`;
        if (!model.bigramCounts[leftBg]) {
          score += 2;
          reasons.push(`unseen bigram: ${leftLabel}→${label}`);
        } else if (model.bigramCounts[leftBg] <= 3) {
          score += 1;
          reasons.push(`rare bigram (≤3×): ${leftLabel}→${label}`);
        }
      }

      if (rightLabel) {
        const rightBg = `${label}|${rightLabel}`;
        if (!model.bigramCounts[rightBg]) {
          score += 2;
          reasons.push(`unseen bigram: ${label}→${rightLabel}`);
        } else if (model.bigramCounts[rightBg] <= 3) {
          score += 1;
          reasons.push(`rare bigram (≤3×): ${label}→${rightLabel}`);
        }
      }

      // ─── Signal 2: Known confusion character (unconditional) ────────────
      if (confusionSet.has(label)) {
        score += 1;
        reasons.push(`confusion char`);
      }

      // ─── Signal 3: Character never seen in training ─────────────────────
      if (!model.charCounts[label]) {
        score += 2;
        reasons.push(`unknown char: ${label}`);
      }

      // ─── Signal 4: Unpaired bracket ─────────────────────────────────────
      if ((label === "[" || label === "]") && !bracketPaired[i]) {
        score += 3;
        reasons.push(`unpaired bracket`);
      }

      // ─── Signal 5: Deletion candidate (tiny blob geometry) ──────────────
      const bbox = tok.geometry?.warped_bbox;
      if (bbox) {
        const w = bbox[2] - bbox[0];
        const h = bbox[3] - bbox[1];
        const area = w * h;
        if (area > 0 && area < model.deletionProfile.keptMinArea) {
          score += 2;
          reasons.push(`tiny blob (area ${area.toFixed(0)})`);
        }
      }

      // ─── Signal 6: Unexpected line position (missing predecessor/successor) ──
      // If this char is the FIRST on the line but almost never starts lines
      // in reviewed data, something may be missing before it.
      // Similarly for last char that never ends lines.
      if (model.lineStartCounts && ti === 0) {
        const totalCount = model.charCounts[label] ?? 0;
        const startCount = model.lineStartCounts[label] ?? 0;
        if (totalCount >= 10) {
          if (startCount === 0) {
            score += 2;
            reasons.push(`never starts lines (possible missing predecessor)`);
          } else {
            const startRatio = startCount / totalCount;
            if (startRatio < 0.02) {
              score += 1;
              reasons.push(`rarely starts lines (<2%, possible missing predecessor)`);
            }
          }
        }
      }
      if (model.lineEndCounts && ti === textIndices.length - 1) {
        const totalCount = model.charCounts[label] ?? 0;
        const endCount = model.lineEndCounts[label] ?? 0;
        if (totalCount >= 10) {
          if (endCount === 0) {
            score += 2;
            reasons.push(`never ends lines (possible missing successor)`);
          } else {
            const endRatio = endCount / totalCount;
            if (endRatio < 0.02) {
              score += 1;
              reasons.push(`rarely ends lines (<2%, possible missing successor)`);
            }
          }
        }
      }

      // ─── Signal 7: Diacritic dominance (missing trema/overline/underdot) ──
      // If this bare char has diacritic variants, check whether any variant
      // dominates in the current bigram context. If so, this char likely
      // needs the diacritic.
      const variants = diacriticVariants.get(label);
      if (variants && variants.length > 0) {
        const bareLeftCount = leftLabel ? (model.bigramCounts[`${leftLabel}|${label}`] ?? 0) : 0;
        const bareRightCount = rightLabel ? (model.bigramCounts[`${label}|${rightLabel}`] ?? 0) : 0;

        let bestVariant: string | null = null;
        let bestRatio = 0;

        for (const v of variants) {
          // Check left context: how often does the variant appear after leftLabel?
          if (leftLabel) {
            const varLeftCount = model.bigramCounts[`${leftLabel}|${v}`] ?? 0;
            if (varLeftCount > 0 && bareLeftCount > 0) {
              const ratio = varLeftCount / bareLeftCount;
              if (ratio > bestRatio) { bestRatio = ratio; bestVariant = v; }
            } else if (varLeftCount > 0 && bareLeftCount === 0) {
              // Variant exists in this context but bare doesn't — very strong
              bestRatio = Infinity;
              bestVariant = v;
            }
          }
          // Check right context: how often does the variant appear before rightLabel?
          if (rightLabel) {
            const varRightCount = model.bigramCounts[`${v}|${rightLabel}`] ?? 0;
            if (varRightCount > 0 && bareRightCount > 0) {
              const ratio = varRightCount / bareRightCount;
              if (ratio > bestRatio) { bestRatio = ratio; bestVariant = v; }
            } else if (varRightCount > 0 && bareRightCount === 0) {
              bestRatio = Infinity;
              bestVariant = v;
            }
          }
        }

        if (bestVariant && bestRatio >= 1.0) {
          // Variant is at least as common as the bare form in this context
          if (bestRatio >= 3.0) {
            score += 2;
            reasons.push(`diacritic variant ${bestVariant} dominates here (${bestRatio === Infinity ? "∞" : bestRatio.toFixed(1)}×)`);
          } else {
            score += 1;
            reasons.push(`diacritic variant ${bestVariant} more common here (${bestRatio.toFixed(1)}×)`);
          }
        }
      }

      // ─── Determine warning level ───────────────────────────────────────
      let level: WarningLevel = "ok";
      if (score >= 4) level = "alert";
      else if (score >= 2) level = "warn";

      if (level !== "ok") {
        warnings.push({
          lineIndex: line.line_index,
          blobId: tok.blob_id,
          level,
          reasons,
        });
      }
    }
  }

  return warnings;
}

/**
 * Compute bracket pairing: returns a boolean map where index i is true
 * if the bracket at position i has a matching partner.
 * Unpaired brackets are suspicious (may be misidentified glyphs).
 */
function computeBracketPairing(labels: (string | null)[]): boolean[] {
  const paired = new Array(labels.length).fill(false);

  // Forward pass: match [ with ]
  const openStack: number[] = [];
  for (let i = 0; i < labels.length; i++) {
    if (labels[i] === "[") {
      openStack.push(i);
    } else if (labels[i] === "]") {
      if (openStack.length > 0) {
        const openIdx = openStack.pop()!;
        paired[openIdx] = true;
        paired[i] = true;
      }
      // else: unmatched ] — remains false
    }
  }
  // Any remaining [ in openStack are unmatched — remain false

  return paired;
}
