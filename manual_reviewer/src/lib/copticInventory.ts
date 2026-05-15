/**
 * Coptic letter inventory + special markers used in the Kephalaia OCR.
 * Source of truth for the CharChooser and keymap.
 */

export interface CopticLetter {
  /** Base unicode character (lowercase). */
  base: string;
  /** Latin transliteration key used for typing. */
  key: string;
  /** Friendly name. */
  name: string;
  /** Common Coptic letter aliases (alternative typing keys). */
  aliases?: string[];
}

/**
 * Coptic Bohairic letters that appear in the Kephalaia + the supralinear
 * stroke + diacritic combining characters. Ordered alphabetically (Coptic
 * order) for the chooser grid.
 */
export const COPTIC_LETTERS: CopticLetter[] = [
  { base: "ⲁ", key: "a", name: "alpha" },
  { base: "ⲃ", key: "b", name: "beta" },
  { base: "ⲅ", key: "g", name: "gamma" },
  { base: "ⲇ", key: "d", name: "delta" },
  { base: "ⲉ", key: "e", name: "epsilon" },
  { base: "ⲋ", key: "6", name: "stigma" },
  { base: "ⲍ", key: "z", name: "zeta" },
  { base: "ⲏ", key: "h", name: "eta", aliases: ["E"] },
  { base: "ⲑ", key: "q", name: "theta", aliases: ["T"] },
  { base: "ⲓ", key: "i", name: "iota" },
  { base: "ⲕ", key: "k", name: "kappa" },
  { base: "ⲗ", key: "l", name: "lambda" },
  { base: "ⲙ", key: "m", name: "mu" },
  { base: "ⲛ", key: "n", name: "nu" },
  { base: "ⲝ", key: "x", name: "ksi" },
  { base: "ⲟ", key: "o", name: "omicron" },
  { base: "ⲡ", key: "p", name: "pi" },
  { base: "ⲣ", key: "r", name: "rho" },
  { base: "ⲥ", key: "s", name: "sigma" },
  { base: "ⲧ", key: "t", name: "tau" },
  { base: "ⲩ", key: "u", name: "upsilon" },
  { base: "ⲫ", key: "f", name: "phi" },
  { base: "ⲭ", key: "c", name: "chi" },
  { base: "ⲯ", key: "y", name: "psi" },
  { base: "ⲱ", key: "w", name: "omega", aliases: ["O"] },
  // Coptic-specific extras
  { base: "ϣ", key: "S", name: "shai" },
  { base: "ϥ", key: "F", name: "fai" },
  { base: "ϩ", key: "H", name: "hori" },
  { base: "ϫ", key: "j", name: "djandja" },
  { base: "ϭ", key: "C", name: "qima" },
  { base: "ϯ", key: "v", name: "ti" },
];

/** Maps Latin key → Coptic base letter (lowercase Coptic). */
export const COPTIC_KEYMAP: Record<string, string> = (() => {
  const m: Record<string, string> = {};
  for (const l of COPTIC_LETTERS) {
    m[l.key] = l.base;
    if (l.aliases) for (const a of l.aliases) m[a] = l.base;
  }
  return m;
})();

/* ----------------------------------------------------------------------------
 * Diacritics (combining characters)
 * ------------------------------------------------------------------------- */

export interface Diacritic {
  /** Combining unicode char appended to the base letter. */
  combining: string;
  /** Chord key (Shift/Alt/Ctrl + letter or symbol). */
  key: string;
  name: string;
}

export const DIACRITICS: Diacritic[] = [
  { combining: "\u0304", key: "Shift+-", name: "overline (macron above)" },
  { combining: "\u0307", key: "Shift+.", name: "dot above" },
  { combining: "\u0308", key: "Shift+:", name: "diaeresis (trema)" },
  { combining: "\u0323", key: "Alt+.", name: "dot below" },
];

export const DIACRITIC_KEYS: Record<string, string> = (() => {
  const m: Record<string, string> = {};
  for (const d of DIACRITICS) m[d.key] = d.combining;
  return m;
})();

/* ----------------------------------------------------------------------------
 * Special markers (non-Coptic editorial / lacuna)
 * ------------------------------------------------------------------------- */

export interface SpecialMarker {
  token: string;
  display: string;
  key?: string;
  name: string;
}

export const SPECIAL_MARKERS: SpecialMarker[] = [
  { token: ".", display: ".", key: ".", name: "lacuna dot" },
  { token: "[", display: "[", key: "[", name: "left bracket" },
  { token: "]", display: "]", key: "]", name: "right bracket" },
];

export const SPECIAL_KEYMAP: Record<string, string> = (() => {
  const m: Record<string, string> = {};
  for (const s of SPECIAL_MARKERS) if (s.key) m[s.key] = s.token;
  return m;
})();
