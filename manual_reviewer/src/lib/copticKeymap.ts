"use client";
import { COPTIC_KEYMAP, DIACRITIC_KEYS, SPECIAL_KEYMAP } from "./copticInventory";

/**
 * Translate a raw KeyboardEvent into a CharChooser intent.
 *
 * Three kinds of intent:
 *   - { kind: "label", label: "ⲁ" }            (Coptic letter via key)
 *   - { kind: "diacritic", combining: "\u0304" } (append to current label)
 *   - { kind: "special", token: "[" }           (Unicode special marker)
 *   - { kind: "control", action: "commit" | "cancel" | "clear" | "next" | "prev" }
 *   - null  -> not a recognised key
 */
export type CharIntent =
  | { kind: "label"; label: string }
  | { kind: "diacritic"; combining: string }
  | { kind: "special"; token: string }
  | { kind: "control"; action: "commit" | "cancel" | "clear" | "next" | "prev" | "candidate"; index?: number }
  | null;

function chordCandidates(e: KeyboardEvent | React.KeyboardEvent): string[] {
  const modifiers: string[] = [];
  if (e.shiftKey) modifiers.push("Shift");
  if (e.altKey) modifiers.push("Alt");
  if (e.ctrlKey) modifiers.push("Ctrl");

  const keys = new Set<string>([e.key]);
  if (e.code === "Minus") keys.add("-");
  if (e.code === "Period") keys.add(".");
  if (e.code === "Semicolon") keys.add(":");
  if (e.key === "_") keys.add("-");
  if (e.key === ">") keys.add(".");

  return [...keys].map((key) => [...modifiers, key].join("+"));
}

export function intentFromKey(e: KeyboardEvent | React.KeyboardEvent): CharIntent {
  const key = e.key;

  // controls
  if (key === "Enter") return { kind: "control", action: "commit" };
  if (key === "Escape") return { kind: "control", action: "cancel" };
  if (key === "Backspace") return { kind: "control", action: "clear" };
  if (key === "Tab") return { kind: "control", action: e.shiftKey ? "prev" : "next" };

  // candidate picker (1..9)
  if (!e.ctrlKey && !e.altKey && /^[1-9]$/.test(key)) {
    return { kind: "control", action: "candidate", index: parseInt(key, 10) - 1 };
  }

  // chord-based diacritics (accept displayed and physical punctuation forms)
  for (const chordKey of chordCandidates(e)) {
    if (DIACRITIC_KEYS[chordKey]) {
      return { kind: "diacritic", combining: DIACRITIC_KEYS[chordKey] };
    }
  }

  // special markers
  if (SPECIAL_KEYMAP[key]) return { kind: "special", token: SPECIAL_KEYMAP[key] };

  // Coptic letter
  if (COPTIC_KEYMAP[key]) return { kind: "label", label: COPTIC_KEYMAP[key] };

  return null;
}

export function applyDiacritic(label: string | null | undefined, combining: string): string {
  if (!label) return combining;
  return label + combining;
}
