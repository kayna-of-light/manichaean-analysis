import "server-only";
import fs from "node:fs";
import fsPromises from "node:fs/promises";
import path from "node:path";
import {
  BaselineSchema,
  BodyBboxSchema,
  LineRecordSchema,
  LinesBaseSplitSchema,
  type Baseline,
  type BodyBbox,
  type LineRecord,
  type LinesBaseSplit,
} from "./zodSchemas";
import { MANUAL_REVIEWER, PIPELINE, PIPELINE_V2 } from "./paths";

const PAGE_FILE_RE = /^keph_p(\d{3,4})_lines_base_split\.json$/;
const BASELINE_FILE_RE = /^p(\d{3,4})\.json$/;

let _pageList: string[] | null = null;
let _lineSeqIndex: Map<string, LineRecord[]> | null = null;
const _baselineCache = new Map<string, { mtimeMs: number; value: Baseline | null }>();

/**
 * Returns sorted list of page ids that exist on disk. Cheap; cached.
 * Page ids are strings (zero-padded, e.g. "010", "100").
 *
 * Source of truth: the transposed initial baseline directory (v2 is leading).
 * Falls back to the v1 split dir if the baseline hasn't been generated yet.
 */
export async function listPages(): Promise<string[]> {
  if (_pageList) return _pageList;
  const baselineDir = MANUAL_REVIEWER.initialBaseline;
  if (fs.existsSync(baselineDir)) {
    const files = await fsPromises.readdir(baselineDir);
    const pages = files
      .map((f) => f.match(BASELINE_FILE_RE)?.[1])
      .filter((p): p is string => Boolean(p))
      .sort();
    if (pages.length > 0) {
      _pageList = pages;
      return pages;
    }
  }
  const dir = PIPELINE.pagesBaseSplitCorrected;
  if (!fs.existsSync(dir)) {
    _pageList = [];
    return _pageList;
  }
  const files = await fsPromises.readdir(dir);
  const pages = files
    .map((f) => f.match(PAGE_FILE_RE)?.[1])
    .filter((p): p is string => Boolean(p))
    .sort();
  _pageList = pages;
  return pages;
}

/**
 * Read the transposed v1→v2 baseline for a page. v2 text_body coords; v1
 * cluster/label state. Cached per-process.
 */
export async function readInitialBaseline(page: string): Promise<Baseline | null> {
  const f = path.join(MANUAL_REVIEWER.initialBaseline, `p${page}.json`);
  if (!fs.existsSync(f)) {
    _baselineCache.set(page, { mtimeMs: -1, value: null });
    return null;
  }
  const mtimeMs = fs.statSync(f).mtimeMs;
  const cached = _baselineCache.get(page);
  if (cached && cached.mtimeMs === mtimeMs) return cached.value;
  const txt = await fsPromises.readFile(f, "utf8");
  const parsed = BaselineSchema.parse(JSON.parse(txt));
  _baselineCache.set(page, { mtimeMs, value: parsed });
  return parsed;
}

export function textBodyImageUrl(page: string): string {
  // Served via /api/image?root=textbody&p=p{NNN}_text_body.jpg
  return `/api/image?root=textbody&p=${encodeURIComponent(`p${page}_text_body.jpg`)}`;
}

export interface V2RowGeometry {
  index: number;
  bbox: [number, number, number, number]; // [x, y, width, height]
  baseline_y: number;
  x_span: [number, number];
}

const _geometryCache = new Map<string, { mtimeMs: number; value: V2RowGeometry[] | null }>();

/**
 * Read the v2 body_geometry for a page. Returns row bboxes (ink extents)
 * which provide accurate crop bounds for line strips.
 */
export async function readV2Geometry(page: string): Promise<V2RowGeometry[] | null> {
  const f = path.join(PIPELINE_V2.bodyGeometryPages, `p${page}_geometry.json`);
  if (!fs.existsSync(f)) {
    _geometryCache.set(page, { mtimeMs: -1, value: null });
    return null;
  }
  const mtimeMs = fs.statSync(f).mtimeMs;
  const cached = _geometryCache.get(page);
  if (cached && cached.mtimeMs === mtimeMs) return cached.value;
  const txt = await fsPromises.readFile(f, "utf8");
  const data = JSON.parse(txt);
  const rows: V2RowGeometry[] = (data.geometry_rows ?? []).map((r: Record<string, unknown>) => ({
    index: r.index as number,
    bbox: r.bbox as [number, number, number, number],
    baseline_y: r.baseline_y as number,
    x_span: r.x_span as [number, number],
  }));
  _geometryCache.set(page, { mtimeMs, value: rows });
  return rows;
}

/**
 * Streams line_sequences.jsonl once, builds an in-memory map page → LineRecord[].
 * The file is large (~50MB) so we only parse it once per process.
 */
export async function getLineSequencesIndex(): Promise<
  Map<string, LineRecord[]>
> {
  if (_lineSeqIndex) return _lineSeqIndex;
  const idx = new Map<string, LineRecord[]>();
  const file = PIPELINE.lineSequences;
  if (!fs.existsSync(file)) {
    _lineSeqIndex = idx;
    return idx;
  }
  // streaming reader to avoid holding the full file in memory twice
  const stream = fs.createReadStream(file, { encoding: "utf8" });
  let buf = "";
  await new Promise<void>((resolve, reject) => {
    stream.on("data", (chunk) => {
      buf += chunk;
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl);
        buf = buf.slice(nl + 1);
        if (!line.trim()) continue;
        try {
          const raw = JSON.parse(line);
          const parsed = LineRecordSchema.parse(raw);
          const bucket = idx.get(parsed.page) ?? [];
          bucket.push(parsed);
          idx.set(parsed.page, bucket);
        } catch {
          // skip malformed line
        }
      }
    });
    stream.on("end", () => {
      if (buf.trim()) {
        try {
          const raw = JSON.parse(buf);
          const parsed = LineRecordSchema.parse(raw);
          const bucket = idx.get(parsed.page) ?? [];
          bucket.push(parsed);
          idx.set(parsed.page, bucket);
        } catch {
          /* ignore trailing */
        }
      }
      resolve();
    });
    stream.on("error", reject);
  });
  // Sort lines within each page
  for (const arr of idx.values()) {
    arr.sort((a, b) => a.line_index - b.line_index);
  }
  _lineSeqIndex = idx;
  return idx;
}

export async function getPageLines(page: string): Promise<LineRecord[]> {
  const idx = await getLineSequencesIndex();
  return idx.get(page) ?? [];
}

export async function readBodyBbox(page: string): Promise<BodyBbox | null> {
  const f = path.join(PIPELINE.pages, `keph_p${page}_body_bbox.json`);
  if (!fs.existsSync(f)) return null;
  const txt = await fsPromises.readFile(f, "utf8");
  return BodyBboxSchema.parse(JSON.parse(txt));
}

export async function readLinesBaseSplit(
  page: string,
): Promise<LinesBaseSplit | null> {
  const f = path.join(
    PIPELINE.pagesBaseSplitCorrected,
    `keph_p${page}_lines_base_split.json`,
  );
  if (!fs.existsSync(f)) return null;
  const txt = await fsPromises.readFile(f, "utf8");
  return LinesBaseSplitSchema.parse(JSON.parse(txt));
}

// ---------- Final Label Index: mark-attached labels from composite pipeline ----------

export interface WitnessToken {
  page: string;
  line_index: number;
  blob_id: number;
  final_label: string | null;
  overline_mark_id: number | null;
  geometry_mark_kinds: string[];
}

/**
 * Cached final_label index: nested { page → line → blob → label | [label, overline_mark_id] }.
 * Built by scripts/projects/manual_reviewer_ingest/build_final_label_index.py
 * from composite_line_sequences.jsonl (the same source the review sheet uses).
 */
let _finalLabelIndex: Record<string, Record<string, Record<string, string | [string, number]>>> | null = null;

async function loadFinalLabelIndex(): Promise<Record<string, Record<string, Record<string, string | [string, number]>>>> {
  if (_finalLabelIndex) return _finalLabelIndex;
  const f = path.join(MANUAL_REVIEWER.initialBaseline, "..", "final_label_index.json");
  if (!fs.existsSync(f)) {
    _finalLabelIndex = {};
    return _finalLabelIndex;
  }
  const txt = await fsPromises.readFile(f, "utf8");
  _finalLabelIndex = JSON.parse(txt);
  return _finalLabelIndex!;
}

/**
 * Get all final_labels for tokens on a page. Returns a Map keyed by
 * "page:line:blob" → WitnessToken.
 */
export async function getWitnessTokensForPage(
  page: string,
): Promise<Map<string, WitnessToken>> {
  const idx = await loadFinalLabelIndex();
  const result = new Map<string, WitnessToken>();
  const pageData = idx[page];
  if (!pageData) return result;
  for (const [lineStr, blobs] of Object.entries(pageData)) {
    const lineIndex = parseInt(lineStr, 10);
    for (const [blobStr, entry] of Object.entries(blobs)) {
      const blobId = parseInt(blobStr, 10);
      const key = `${page}:${lineIndex}:${blobId}`;
      let finalLabel: string;
      let overlineMarkId: number | null = null;
      if (Array.isArray(entry)) {
        finalLabel = entry[0];
        overlineMarkId = entry[1];
      } else {
        finalLabel = entry;
      }
      result.set(key, {
        page,
        line_index: lineIndex,
        blob_id: blobId,
        final_label: finalLabel,
        overline_mark_id: overlineMarkId,
        geometry_mark_kinds: [],
      });
    }
  }
  return result;
}

export function bodyImagePath(page: string): string {
  return path.join(PIPELINE.pages, `keph_p${page}_body.jpg`);
}

/** Resolve a cluster thumbnail by id (cluster as integer or 3-digit string). */
export function clusterThumbnails(clusterId: string): string[] {
  const dir = PIPELINE.clusters;
  if (!fs.existsSync(dir)) return [];
  const cid = clusterId.toString().padStart(3, "0");
  const prefix = `c_${cid}_`;
  return fs
    .readdirSync(dir)
    .filter((f) => f.startsWith(prefix) && f.endsWith(".png"))
    .map((f) => path.join(dir, f));
}
