import path from "node:path";
import fs from "node:fs";

/**
 * Resolves the location of pipeline outputs (read-only) and our SQLite data dir.
 * Configurable via env vars so we can point at different paginations or move
 * the db without redeploying.
 */
const repoRoot = path.resolve(process.cwd(), "..");

export const PIPELINE_DIR =
  process.env.KEPH_OUTPUT_DIR ??
  path.join(repoRoot, "output", "projects", "kephalaia_ocr");

/** Root for v2 pipeline outputs (line_body_split + body_geometry). */
export const PIPELINE_V2_DIR =
  process.env.KEPH_OUTPUT_V2_DIR ??
  path.join(repoRoot, "output", "projects", "kephalaia_ocr_v2");

/** Root for the manual-reviewer-specific ingest layer (transposed baseline). */
export const MANUAL_REVIEWER_DIR =
  process.env.KEPH_MANUAL_REVIEWER_DIR ??
  path.join(repoRoot, "output", "projects", "kephalaia_manual_reviewer");

export const DATA_DIR =
  process.env.KEPH_DATA_DIR ?? path.join(process.cwd(), "data");

export const DB_PATH = path.join(DATA_DIR, "reviewer.db");
export const BACKUP_DIR = path.join(DATA_DIR, "backups");
export const EXPORT_DIR = path.join(DATA_DIR, "exports");

export function ensureDataDirs() {
  for (const dir of [DATA_DIR, BACKUP_DIR, EXPORT_DIR]) {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }
}

/** Pipeline subpaths — keep these in one place. */
const CLUSTER_K = process.env.KEPH_CLUSTER_K ?? "clusters_shape_padded_split_bodycrop_corrected_k240";

export const PIPELINE = {
  pages: path.join(PIPELINE_DIR, "pages"),
  pagesBaseSplitCorrected: path.join(
    PIPELINE_DIR,
    "pages_base_split_chars_bodycrop_corrected",
  ),
  /** Top-level cluster artifacts (thumbnails + _assignments.json live here). */
  clusters: path.join(PIPELINE_DIR, CLUSTER_K),
  clusterAssignments: path.join(PIPELINE_DIR, CLUSTER_K, "_assignments.json"),
  subclusters: path.join(PIPELINE_DIR, CLUSTER_K, "subclusters"),
  /** Analytic outputs under contextual_review/<cluster_set>/. */
  contextualReview: path.join(PIPELINE_DIR, "contextual_review", CLUSTER_K),
  lineSequences: path.join(
    PIPELINE_DIR,
    "contextual_review",
    CLUSTER_K,
    "line_sequences.jsonl",
  ),
  llmWitness: path.join(
    PIPELINE_DIR,
    "llm_witness",
    CLUSTER_K,
    "review_llm_witness.json",
  ),
};

/** v2 ingest paths. v2 body crop + body_geometry is the leading canvas. */
export const PIPELINE_V2 = {
  pagesCropped: path.join(PIPELINE_V2_DIR, "pages_cropped"),
  textBody: path.join(PIPELINE_V2_DIR, "line_body_split", "text_body"),
  lineBodyMetadata: path.join(PIPELINE_V2_DIR, "line_body_split", "metadata"),
  bodyGeometryPages: path.join(PIPELINE_V2_DIR, "body_geometry", "pages"),
  bodyGeometryMasks: path.join(PIPELINE_V2_DIR, "body_geometry", "masks"),
};

/** Manual-reviewer ingest artifacts. */
export const MANUAL_REVIEWER = {
  initialBaseline: path.join(MANUAL_REVIEWER_DIR, "initial_baseline"),
  summary: path.join(MANUAL_REVIEWER_DIR, "summary.json"),
};

/**
 * Whitelist for the /api/image proxy. Each entry is {key, dir}; the
 * `?root=` query param selects which entry to resolve `?p=` under.
 */
export const IMAGE_ROOTS: { key: string; dir: string }[] = [
  { key: "pages", dir: PIPELINE.pages },
  { key: "clusters", dir: PIPELINE.clusters },
  { key: "textbody", dir: PIPELINE_V2.textBody },
  { key: "pages_v2", dir: PIPELINE_V2.pagesCropped },
];
