import "server-only";
import editorialSeedRaw from "../data/editorialSeed.json";
import { getDb } from "./db";
import {
  readActiveEditorialArraysWithSentences,
  readEditorialClusterArrays,
  readEditorialSentences,
  readReassignmentsForPage,
  type ClusterReassignmentRow,
  type EditorialArrayWithSentence,
  type EditorialClusterArrayRow,
  type EditorialTokenOverlay,
} from "./repo";
import {
  listPages,
  readInitialBaseline,
  textBodyImageUrl,
} from "./pipelineReaders";
import type { Baseline, BaselineToken } from "./zodSchemas";

export interface EditorialMatchPreview {
  page: string;
  line_index: number;
  v1_line_index: number | null;
  token_count: number;
  token_keys: string[];
  blob_ids: number[];
  image_url: string;
  image_size: [number, number] | null;
  aabb: [number, number, number, number] | null;
}

export interface EditorialArrayView extends EditorialClusterArrayRow {
  cluster_array: number[];
  length: number;
  char_count_no_spaces: number;
  length_matches_sentence: boolean;
  match_count: number;
  matches: EditorialMatchPreview[];
}

export interface EditorialSentenceView {
  id: number;
  text: string;
  active: number;
  note: string | null;
  created_at: string;
  updated_at: string;
  chars_no_spaces: string[];
  char_count_no_spaces: number;
  arrays: EditorialArrayView[];
}

interface LiveToken {
  page: string;
  line_index: number;
  v1_line_index: number | null;
  blob_id: number;
  cluster: number | null;
  token: BaselineToken;
}

type EditorialSeedDataset = Record<string, number[][]>;

const EDITORIAL_SEED_DATASET = editorialSeedRaw as EditorialSeedDataset;
const EDITORIAL_SEED_META_KEY = "editorial_seed_dataset_version";
const EDITORIAL_SEED_VERSION = "2026-05-18-editorial-fingerprints-v1";
const EDITORIAL_SEED_NOTE = "seeded from editorial fingerprint dataset";

export function sentenceCharsNoSpaces(text: string): string[] {
  return [...text].filter((ch) => !/\s/u.test(ch));
}

export function parseClusterArray(value: string): number[] {
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => Number(item))
      .filter((item) => Number.isInteger(item));
  } catch {
    return [];
  }
}

function readEditorialSeedEntries(): Array<[string, number[][]]> {
  return Object.entries(EDITORIAL_SEED_DATASET).map(([text, arrays]) => {
    if (!Array.isArray(arrays)) {
      throw new Error(`Invalid editorial seed entry for ${text}: arrays must be a list`);
    }
    const charCount = sentenceCharsNoSpaces(text).length;
    for (const clusters of arrays) {
      if (
        !Array.isArray(clusters) ||
        clusters.some((cluster) => !Number.isInteger(cluster))
      ) {
        throw new Error(`Invalid editorial seed array for ${text}: clusters must be integers`);
      }
      if (clusters.length !== charCount) {
        throw new Error(
          `Invalid editorial seed array for ${text}: ${clusters.length} clusters for ${charCount} characters`,
        );
      }
    }
    return [text, arrays];
  });
}

export function maybeSeedEditorialDataset(): void {
  const db = getDb();
  const seeded = db
    .prepare<[string], { value: string }>("SELECT value FROM meta WHERE key = ?")
    .get(EDITORIAL_SEED_META_KEY);
  if (seeded?.value === EDITORIAL_SEED_VERSION) return;

  const sentenceCount = db
    .prepare<[], { count: number }>("SELECT COUNT(*) AS count FROM editorial_sentences")
    .get()?.count ?? 0;
  const arrayCount = db
    .prepare<[], { count: number }>("SELECT COUNT(*) AS count FROM editorial_cluster_arrays")
    .get()?.count ?? 0;
  const legacySeeded = db
    .prepare<[string], { value: string }>("SELECT value FROM meta WHERE key = ?")
    .get("editorial_inventory_seeded");

  const canSeedEmptyDb = sentenceCount === 0 && arrayCount === 0;
  const canReplaceLegacyPhraseSeed = legacySeeded?.value === "1" && arrayCount === 0;
  if (!canSeedEmptyDb && !canReplaceLegacyPhraseSeed) return;

  const entries = readEditorialSeedEntries();
  const now = new Date().toISOString();
  const tx = db.transaction(() => {
    if (canReplaceLegacyPhraseSeed) {
      db.prepare("DELETE FROM editorial_cluster_arrays").run();
      db.prepare("DELETE FROM editorial_sentences").run();
    }

    const insertSentence = db.prepare(
      `INSERT INTO editorial_sentences (text, active, note, created_at, updated_at)
       VALUES (@text, 1, @note, datetime('now'), @updated_at)
       ON CONFLICT(text) DO UPDATE SET
         active = excluded.active,
         note = excluded.note,
         updated_at = excluded.updated_at`,
    );
    const readSentenceId = db.prepare<[string], { id: number }>(
      "SELECT id FROM editorial_sentences WHERE text = ?",
    );
    const insertArray = db.prepare(
      `INSERT INTO editorial_cluster_arrays
       (sentence_id, name, clusters, active, created_at, updated_at)
       VALUES (@sentence_id, @name, @clusters, 1, datetime('now'), @updated_at)`,
    );

    for (const [text, arrays] of entries) {
      insertSentence.run({ text, note: EDITORIAL_SEED_NOTE, updated_at: now });
      const sentence = readSentenceId.get(text);
      if (!sentence) throw new Error(`Failed to seed editorial sentence: ${text}`);
      arrays.forEach((clusters, index) => {
        insertArray.run({
          sentence_id: sentence.id,
          name: arrays.length > 1 ? `seed ${index + 1}` : null,
          clusters: JSON.stringify(clusters),
          updated_at: now,
        });
      });
    }

    db.prepare(
      "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
    ).run(EDITORIAL_SEED_META_KEY, EDITORIAL_SEED_VERSION);
    db.prepare(
      "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
    ).run("editorial_inventory_seeded", `replaced-by-${EDITORIAL_SEED_VERSION}`);
  });
  tx.immediate();
}

function tokenKey(lineIndex: number, blobId: number | string): string {
  return `${lineIndex}:${blobId}`;
}

function effectiveCluster(
  token: BaselineToken,
  lineIndex: number,
  reassignments: Map<string, ClusterReassignmentRow>,
): number | null {
  const reassignment = reassignments.get(tokenKey(lineIndex, token.blob_id));
  if (reassignment) return reassignment.to_cluster;
  const parsed = Number(token.cluster);
  return Number.isFinite(parsed) ? parsed : null;
}

function liveLinesForBaseline(
  page: string,
  baseline: Baseline,
  unsetSet: Set<string>,
  reassignments: Map<string, ClusterReassignmentRow>,
): LiveToken[][] {
  return baseline.lines.map((line) =>
    line.tokens
      .filter((token) => !unsetSet.has(tokenKey(line.line_index, token.blob_id)))
      .map((token) => ({
        page,
        line_index: line.line_index,
        v1_line_index: token.v1_line_index ?? line.v1_line_index ?? null,
        blob_id: token.blob_id,
        cluster: effectiveCluster(token, line.line_index, reassignments),
        token,
      })),
  );
}

function aabbUnion(tokens: LiveToken[]): [number, number, number, number] | null {
  const boxes = tokens.map((item) => item.token.geometry.aabb).filter(Boolean);
  if (boxes.length === 0) return null;
  return [
    Math.min(...boxes.map((box) => box[0])),
    Math.min(...boxes.map((box) => box[1])),
    Math.max(...boxes.map((box) => box[2])),
    Math.max(...boxes.map((box) => box[3])),
  ];
}

/** Sentinel cluster IDs for wildcard patterns. */
export const WILDCARD_SINGLE = -2; // "." — match any single token
export const WILDCARD_MULTI = -3;  // "*" — match any sequence of tokens

/** Returns true if the pattern contains any wildcard sentinels. */
function patternHasWildcard(clusters: number[]): boolean {
  return clusters.some((c) => c === WILDCARD_SINGLE || c === WILDCARD_MULTI);
}

/**
 * Exact match (no wildcards). Tokens must be exactly the same length as the
 * pattern and each cluster must match.
 */
function clustersMatchExact(tokens: LiveToken[], clusters: number[]): boolean {
  if (tokens.length !== clusters.length) return false;
  return tokens.every((token, index) => token.cluster === clusters[index]);
}

/**
 * Pattern match with wildcards. Returns all sub-sequences of `lineTokens`
 * (starting at `start`) that match the pattern. Returns the matched token
 * windows (may be multiple due to `*` greediness options).
 */
function patternMatchAt(
  lineTokens: LiveToken[],
  start: number,
  pattern: number[],
  minLength: number | null,
  maxLength: number | null,
): LiveToken[][] {
  const results: LiveToken[][] = [];

  function recurse(ti: number, pi: number, matched: LiveToken[]): void {
    // Pattern exhausted — we have a match if length constraints are satisfied.
    if (pi >= pattern.length) {
      const len = matched.length;
      if (minLength != null && len < minLength) return;
      if (maxLength != null && len > maxLength) return;
      results.push([...matched]);
      return;
    }
    // Token stream exhausted but pattern remains.
    if (ti >= lineTokens.length) return;

    const p = pattern[pi];
    if (p === WILDCARD_MULTI) {
      // "*" matches zero or more tokens. Try consuming 0..N tokens.
      // First try zero-width match (skip the wildcard).
      recurse(ti, pi + 1, matched);
      // Then try consuming tokens one at a time.
      for (let eat = 1; ti + eat <= lineTokens.length; eat++) {
        const nextMatched = [...matched, ...lineTokens.slice(ti, ti + eat)];
        if (maxLength != null && nextMatched.length > maxLength) break;
        recurse(ti + eat, pi + 1, nextMatched);
      }
    } else if (p === WILDCARD_SINGLE) {
      // "." matches exactly one token (any cluster).
      matched.push(lineTokens[ti]);
      recurse(ti + 1, pi + 1, matched);
      matched.pop();
    } else {
      // Literal cluster match.
      if (lineTokens[ti].cluster === p) {
        matched.push(lineTokens[ti]);
        recurse(ti + 1, pi + 1, matched);
        matched.pop();
      }
    }
  }

  recurse(start, 0, []);
  return results;
}

function matchArrayOnBaseline(
  page: string,
  baseline: Baseline,
  clusters: number[],
  minLength: number | null,
  maxLength: number | null,
  reassignments: Map<string, ClusterReassignmentRow>,
  unsetSet: Set<string>,
): EditorialMatchPreview[] {
  if (clusters.length === 0) return [];
  const imageUrl = textBodyImageUrl(page);
  const liveLines = liveLinesForBaseline(page, baseline, unsetSet, reassignments);
  const matches: EditorialMatchPreview[] = [];
  const hasWildcard = patternHasWildcard(clusters);

  for (const lineTokens of liveLines) {
    if (!hasWildcard) {
      // Fast path: exact length matching.
      if (lineTokens.length < clusters.length) continue;
      for (let start = 0; start <= lineTokens.length - clusters.length; start += 1) {
        const window = lineTokens.slice(start, start + clusters.length);
        if (!clustersMatchExact(window, clusters)) continue;
        matches.push({
          page,
          line_index: window[0].line_index,
          v1_line_index: window[0].v1_line_index,
          token_count: window.length,
          token_keys: window.map((token) => tokenKey(token.line_index, token.blob_id)),
          blob_ids: window.map((token) => token.blob_id),
          image_url: imageUrl,
          image_size: baseline.image_size,
          aabb: aabbUnion(window),
        });
      }
    } else {
      // Wildcard pattern matching.
      const seen = new Set<string>();
      for (let start = 0; start < lineTokens.length; start += 1) {
        const windowMatches = patternMatchAt(lineTokens, start, clusters, minLength, maxLength);
        for (const window of windowMatches) {
          if (window.length === 0) continue;
          // De-duplicate by start position + length.
          const key = `${start}:${window.length}`;
          if (seen.has(key)) continue;
          seen.add(key);
          matches.push({
            page,
            line_index: window[0].line_index,
            v1_line_index: window[0].v1_line_index,
            token_count: window.length,
            token_keys: window.map((token) => tokenKey(token.line_index, token.blob_id)),
            blob_ids: window.map((token) => token.blob_id),
            image_url: imageUrl,
            image_size: baseline.image_size,
            aabb: aabbUnion(window),
          });
        }
      }
    }
  }
  return matches;
}

function getUnsetSet(pageInt: number): Set<string> {
  const db = getDb();
  const rows = db
    .prepare<[number], { line_index: number; blob_id: string }>(
      "SELECT line_index, blob_id FROM unset_blobs WHERE page = ?",
    )
    .all(pageInt);
  return new Set(rows.map((row) => tokenKey(row.line_index, row.blob_id)));
}

export async function findEditorialMatchesForArray(
  clusters: number[],
  minLength?: number | null,
  maxLength?: number | null,
): Promise<EditorialMatchPreview[]> {
  const pages = await listPages();
  const matches: EditorialMatchPreview[] = [];
  for (const page of pages) {
    const baseline = await readInitialBaseline(page);
    if (!baseline) continue;
    const pageInt = Number(page);
    const reassignments = readReassignmentsForPage(pageInt);
    const unsetSet = getUnsetSet(pageInt);
    matches.push(...matchArrayOnBaseline(page, baseline, clusters, minLength ?? null, maxLength ?? null, reassignments, unsetSet));
  }
  return matches;
}

export async function buildEditorialOverview(): Promise<EditorialSentenceView[]> {
  maybeSeedEditorialDataset();
  const sentences = readEditorialSentences();
  const arrays = readEditorialClusterArrays();
  const arraysBySentence = new Map<number, EditorialArrayView[]>();
  for (const row of arrays) {
    const clusters = parseClusterArray(row.clusters);
    const sentence = sentences.find((item) => item.id === row.sentence_id);
    const chars = sentence ? sentenceCharsNoSpaces(sentence.text) : [];
    const matches = await findEditorialMatchesForArray(clusters, row.min_length, row.max_length);
    const view: EditorialArrayView = {
      ...row,
      cluster_array: clusters,
      length: clusters.length,
      char_count_no_spaces: chars.length,
      length_matches_sentence: clusters.length === chars.length,
      match_count: matches.length,
      matches,
    };
    const bucket = arraysBySentence.get(row.sentence_id) ?? [];
    bucket.push(view);
    arraysBySentence.set(row.sentence_id, bucket);
  }
  return sentences.map((sentence) => {
    const chars = sentenceCharsNoSpaces(sentence.text);
    return {
      ...sentence,
      chars_no_spaces: chars,
      char_count_no_spaces: chars.length,
      arrays: arraysBySentence.get(sentence.id) ?? [],
    };
  });
}

export async function buildEditorialOverlayForPage(
  page: string,
  baseline: Baseline,
  unsetSet: Set<string>,
  reassignments: Map<string, ClusterReassignmentRow>,
): Promise<Map<string, EditorialTokenOverlay>> {
  maybeSeedEditorialDataset();
  const rows = readActiveEditorialArraysWithSentences();
  const overlay = new Map<string, EditorialTokenOverlay>();
  if (rows.length === 0) return overlay;

  const liveLines = liveLinesForBaseline(page, baseline, unsetSet, reassignments);
  for (const row of rows) {
    applyArrayOverlay(row, liveLines, overlay);
  }
  return overlay;
}

function applyArrayOverlay(
  row: EditorialArrayWithSentence,
  liveLines: LiveToken[][],
  overlay: Map<string, EditorialTokenOverlay>,
) {
  const clusters = parseClusterArray(row.clusters);
  const chars = sentenceCharsNoSpaces(row.sentence_text);
  if (clusters.length === 0 || clusters.length !== chars.length) return;
  const hasWildcard = patternHasWildcard(clusters);
  for (const lineTokens of liveLines) {
    if (!hasWildcard) {
      if (lineTokens.length < clusters.length) continue;
      for (let start = 0; start <= lineTokens.length - clusters.length; start += 1) {
        const window = lineTokens.slice(start, start + clusters.length);
        if (!clustersMatchExact(window, clusters)) continue;
        applyOverlayWindow(row, clusters, chars, window, overlay);
      }
      continue;
    }

    const seen = new Set<string>();
    for (let start = 0; start < lineTokens.length; start += 1) {
      const windowMatches = patternMatchAt(
        lineTokens,
        start,
        clusters,
        row.min_length,
        row.max_length,
      );
      for (const window of windowMatches) {
        if (window.length !== chars.length) continue;
        const key = `${start}:${window.length}`;
        if (seen.has(key)) continue;
        seen.add(key);
        applyOverlayWindow(row, clusters, chars, window, overlay);
      }
    }
  }
}

function applyOverlayWindow(
  row: EditorialArrayWithSentence,
  clusters: number[],
  chars: string[],
  window: LiveToken[],
  overlay: Map<string, EditorialTokenOverlay>,
) {
  for (let index = 0; index < window.length; index += 1) {
    const token = window[index];
    const key = tokenKey(token.line_index, token.blob_id);
    if (overlay.has(key)) continue;
    overlay.set(key, {
      label: chars[index],
      sentence_id: row.sentence_id,
      array_id: row.id,
      sentence_text: row.sentence_text,
      span_position: index,
      span_count: chars.length,
      cluster_array: clusters,
    });
  }
}