#!/usr/bin/env node
/**
 * build_bigram_model.js
 *
 * Reads the first N reviewed pages (with corrections applied from the DB),
 * builds a character bigram frequency model + confusion pairs + deletion geometry profile,
 * and writes the model to data/bigram_model.json.
 *
 * Usage:
 *   node scripts/build_bigram_model.js [--pages 10-34]
 */

const fs = require("fs");
const path = require("path");
const Database = require("better-sqlite3");

const DB_PATH = path.join(__dirname, "..", "data", "reviewer.db");
const BASELINE_DIR = path.join(__dirname, "..", "data", "ingest", "initial_baseline");
const OUTPUT_PATH = path.join(__dirname, "..", "data", "bigram_model.json");

// Parse args
let pageStart = 10;
let pageEnd = 34;
const pagesArg = process.argv.find((a) => a.startsWith("--pages"));
if (pagesArg) {
  const idx = process.argv.indexOf(pagesArg);
  const range = process.argv[idx + 1] || pagesArg.split("=")[1];
  if (range && range.includes("-")) {
    const [s, e] = range.split("-").map(Number);
    if (!isNaN(s) && !isNaN(e)) { pageStart = s; pageEnd = e; }
  }
}

const db = new Database(DB_PATH, { readonly: true });

// ─── Build corrected text and statistics ─────────────────────────────────────

const bigramCounts = {};
const charCounts = {};
let totalBigrams = 0;
let totalChars = 0;

// Confusion pairs: original label -> corrected label
const confusionPairs = {};
// Characters known to be confusing (high error rate)
const confusionChars = new Set();

// Deletion geometry profile
const deletedGeometry = [];
const keptGeometry = [];

// Position tracking: how often each char appears at line-start/line-end
const lineStartCounts = {};  // char → count of times it's the first non-placeholder on a line
const lineEndCounts = {};    // char → count of times it's the last non-placeholder on a line

for (let p = pageStart; p <= pageEnd; p++) {
  const pf = path.join(BASELINE_DIR, `p${String(p).padStart(3, "0")}.json`);
  if (!fs.existsSync(pf)) continue;

  const page = JSON.parse(fs.readFileSync(pf, "utf8"));
  const edits = db.prepare("SELECT line_index, blob_id, label, deleted FROM blob_edits WHERE page = ?").all(p);
  const editMap = new Map(edits.map((e) => [`${e.line_index}:${e.blob_id}`, e]));

  for (const line of page.lines) {
    const lineLabels = [];

    for (const tok of line.tokens) {
      const key = `${line.line_index}:${tok.blob_id}`;
      const ed = editMap.get(key);

      // Track geometry for deletion model
      const geom = tok.geometry;
      if (geom && geom.warped_bbox) {
        const [x0, y0, x1, y1] = geom.warped_bbox;
        const w = x1 - x0;
        const h = y1 - y0;
        const aspect = w / Math.max(h, 0.1);
        const area = w * h;
        const entry = { w, h, aspect, area };

        if (ed && ed.deleted) {
          deletedGeometry.push(entry);
          continue; // Skip deleted tokens
        } else {
          keptGeometry.push(entry);
        }
      } else if (ed && ed.deleted) {
        continue;
      }

      // Determine effective label
      const effectiveLabel = (ed && ed.label) ? ed.label : tok.label;
      if (!effectiveLabel) continue;

      // Track confusion pairs
      if (ed && ed.label && tok.label && ed.label !== tok.label && !ed.deleted) {
        const pair = `${tok.label}\u2192${ed.label}`;
        confusionPairs[pair] = (confusionPairs[pair] || 0) + 1;
        confusionChars.add(tok.label);
      }

      lineLabels.push(effectiveLabel);
    }

    // Build bigrams
    const PLACEHOLDER = new Set(["E", "?"]);
    // Filter to non-placeholder labels for bigram/position analysis
    const textLabels = lineLabels.filter((l) => !PLACEHOLDER.has(l));

    for (let i = 0; i < textLabels.length - 1; i++) {
      const bg = `${textLabels[i]}|${textLabels[i + 1]}`;
      bigramCounts[bg] = (bigramCounts[bg] || 0) + 1;
      totalBigrams++;
      charCounts[textLabels[i]] = (charCounts[textLabels[i]] || 0) + 1;
      totalChars++;
    }
    if (textLabels.length > 0) {
      const last = textLabels[textLabels.length - 1];
      charCounts[last] = (charCounts[last] || 0) + 1;
      totalChars++;

      // Track line-start and line-end chars
      const first = textLabels[0];
      lineStartCounts[first] = (lineStartCounts[first] || 0) + 1;
      lineEndCounts[last] = (lineEndCounts[last] || 0) + 1;
    }
  }
}

db.close();

// ─── Compute deletion geometry thresholds ────────────────────────────────────

function percentile(arr, p) {
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.floor(sorted.length * p);
  return sorted[Math.min(idx, sorted.length - 1)];
}

const deletionProfile = {
  count: deletedGeometry.length,
  medianArea: deletedGeometry.length > 0 ? percentile(deletedGeometry.map((g) => g.area), 0.5) : 0,
  p75Area: deletedGeometry.length > 0 ? percentile(deletedGeometry.map((g) => g.area), 0.75) : 0,
  medianAspect: deletedGeometry.length > 0 ? percentile(deletedGeometry.map((g) => g.aspect), 0.5) : 0,
  areaThreshold: deletedGeometry.length > 0 ? percentile(deletedGeometry.map((g) => g.area), 0.8) : 0,
  keptMinArea: keptGeometry.length > 0 ? percentile(keptGeometry.map((g) => g.area), 0.05) : 0,
};

// ─── Output model ────────────────────────────────────────────────────────────

const model = {
  version: 2,
  generated_at: new Date().toISOString(),
  pages_used: `${pageStart}-${pageEnd}`,
  stats: {
    totalChars,
    totalBigrams,
    uniqueChars: Object.keys(charCounts).length,
    uniqueBigrams: Object.keys(bigramCounts).length,
    confusionPairsCount: Object.keys(confusionPairs).length,
    deletedBlobsTraining: deletedGeometry.length,
    totalLines: Object.values(lineStartCounts).reduce((a, b) => a + b, 0),
  },
  charCounts,
  bigramCounts,
  confusionPairs,
  confusionChars: [...confusionChars],
  deletionProfile,
  lineStartCounts,
  lineEndCounts,
};

fs.writeFileSync(OUTPUT_PATH, JSON.stringify(model, null, 2));

console.log(`Done. Model written to ${OUTPUT_PATH}`);
console.log(`  Pages: ${pageStart}-${pageEnd}`);
console.log(`  ${totalChars} chars, ${totalBigrams} bigrams (${Object.keys(bigramCounts).length} unique)`);
console.log(`  ${Object.keys(confusionPairs).length} confusion pairs from ${confusionChars.size} problematic chars`);
console.log(`  ${deletedGeometry.length} deleted blobs profiled`);
