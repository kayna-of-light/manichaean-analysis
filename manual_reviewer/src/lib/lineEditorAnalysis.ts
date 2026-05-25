import "server-only";
import fs from "node:fs";
import fsPromises from "node:fs/promises";
import path from "node:path";
import { buildCanonicalLineLayout, canonicalizeLineIndex, sourceIndicesForCanonicalLine } from "./canonicalLines";
import { PIPELINE_V2 } from "./paths";
import type { NewBboxRow } from "./repo";
import type { V2RowGeometry } from "./pipelineReaders";

export interface LineEditorBox {
  id: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  label: string | null;
  source: "proposal" | "existing";
  source_component_ids: number[];
  split_method: string;
  confidence: "strong" | "usable" | "needs_review" | "reference";
  kind: "base" | "lacuna_dot" | "mark";
  include: boolean;
}

export interface LineEditorComponent {
  id: number;
  bbox: [number, number, number, number];
  kind: "base" | "dot" | "horizontal" | "excluded" | "other";
  area_px: number;
}

export interface LineEditorTemplateInfo {
  label: string;
  label_slug: string;
  sample_count: number | null;
}

export interface LineEditorPayload {
  page: string;
  page_int: number;
  line_index: number;
  display_index: number;
  source_indices: number[];
  image_size: [number, number];
  image_url: string;
  row_bbox: [number, number, number, number];
  components: LineEditorComponent[];
  proposals: LineEditorBox[];
  existing_bboxes: LineEditorBox[];
  templates: LineEditorTemplateInfo[];
}

interface RawGeometryPage {
  page: string;
  input: string;
  image_size: [number, number];
  scale: number;
  geometry_rows: RawGeometryRow[];
  components: RawComponent[];
}

interface RawGeometryRow extends V2RowGeometry {
  component_ids?: number[];
  baseline_segments?: number[][][];
  median_line_segments?: number[][][];
}

interface RawComponent {
  id: number;
  bbox: [number, number, number, number];
  bbox_scaled?: [number, number, number, number];
  polygon_scaled?: [number, number][];
  area_px?: number;
  is_dot_like?: boolean;
  is_thin_horizontal_mark?: boolean;
  edge?: { is_edge_artifact?: boolean };
  artifact?: {
    is_excluded?: boolean;
    dot_row_supported?: boolean;
    small_lacuna_row_supported?: boolean;
    near_character_supported?: boolean;
  };
}

interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface MaskData {
  mask: Uint8Array;
  width: number;
  height: number;
  originScaled: [number, number];
  scale: number;
}

const LINE_EDITOR_PREVIEW_PAD_X = 30;
const LINE_EDITOR_PREVIEW_PAD_Y = 16;

const TEMPLATE_DIR = path.resolve(
  process.cwd(),
  "..",
  "temp",
  "projects",
  "kephalaia_ocr_v2",
  "glyph_seed_library",
  "manual_template_line_profiles",
);

function geometryPath(page: string) {
  return path.join(PIPELINE_V2.bodyGeometryPages, `p${page}_geometry.json`);
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function boxFromValues(values: number[]): Box {
  return { left: values[0], top: values[1], width: values[2], height: values[3] };
}

function boxRight(box: Box): number {
  return box.left + box.width;
}

function boxBottom(box: Box): number {
  return box.top + box.height;
}

function boxCenterX(box: Box): number {
  return box.left + box.width / 2;
}

function boxCenterY(box: Box): number {
  return box.top + box.height / 2;
}

function boxToXyxy(box: Box): [number, number, number, number] {
  return [round2(box.left), round2(box.top), round2(boxRight(box)), round2(boxBottom(box))];
}

function expandBox(box: Box, padX: number, padY: number, imageSize: [number, number]): Box {
  const left = Math.max(0, box.left - padX);
  const top = Math.max(0, box.top - padY);
  const right = Math.min(imageSize[0], boxRight(box) + padX);
  const bottom = Math.min(imageSize[1], boxBottom(box) + padY);
  return { left, top, width: Math.max(1, right - left), height: Math.max(1, bottom - top) };
}

function boxesIntersect(a: Box, b: Box): boolean {
  return a.left < boxRight(b) && boxRight(a) > b.left && a.top < boxBottom(b) && boxBottom(a) > b.top;
}

function componentBox(component: RawComponent): Box {
  return boxFromValues(component.bbox);
}

function componentIsExcluded(component: RawComponent): boolean {
  return Boolean(component.edge?.is_edge_artifact || component.artifact?.is_excluded);
}

function isHorizontalMark(component: RawComponent): boolean {
  const box = componentBox(component);
  const area = component.area_px ?? 0;
  const aspect = box.width / Math.max(1, box.height);
  return Boolean(
    component.is_thin_horizontal_mark ||
    (box.width >= 6 && box.height <= 7.5 && aspect >= 2.2 && area <= Math.max(160, box.width * 10))
  );
}

function isDotMark(component: RawComponent): boolean {
  const box = componentBox(component);
  const area = component.area_px ?? 0;
  const aspect = box.width / Math.max(1, box.height);
  return Boolean(
    component.is_dot_like ||
    (box.width <= 10 && box.height <= 10 && area <= 80 && aspect >= 0.35 && aspect <= 2.8)
  );
}

function isLacunaDotCharacter(component: RawComponent): boolean {
  if (!isDotMark(component)) return false;
  const artifact = component.artifact;
  if (!artifact) return false;
  return Boolean(artifact.small_lacuna_row_supported || artifact.dot_row_supported);
}

function baselineYAtX(row: RawGeometryRow, xCoord: number): number {
  const segments = row.baseline_segments ?? row.median_line_segments ?? [];
  const points: number[][] = [];
  for (const polyline of segments) {
    const linePoints = polyline.map((point) => [Number(point[0]), Number(point[1])]);
    points.push(...linePoints);
    for (let index = 0; index < linePoints.length - 1; index += 1) {
      const [leftX, leftY] = linePoints[index];
      const [rightX, rightY] = linePoints[index + 1];
      const minX = Math.min(leftX, rightX);
      const maxX = Math.max(leftX, rightX);
      if (xCoord >= minX - 0.5 && xCoord <= maxX + 0.5) {
        const deltaX = rightX - leftX;
        if (Math.abs(deltaX) < 0.001) return (leftY + rightY) / 2;
        const fraction = (xCoord - leftX) / deltaX;
        return leftY + fraction * (rightY - leftY);
      }
    }
  }
  if (points.length) {
    const nearest = points.reduce((best, point) => (
      Math.abs(point[0] - xCoord) < Math.abs(best[0] - xCoord) ? point : best
    ));
    return nearest[1];
  }
  return Number(row.baseline_y ?? 0);
}

function isBaseComponent(component: RawComponent, row: RawGeometryRow): boolean {
  if (componentIsExcluded(component) || isDotMark(component) || isHorizontalMark(component)) return false;
  const box = componentBox(component);
  const area = component.area_px ?? 0;
  if (box.width < 2 || box.height < 5 || area < 10) return false;
  const baselineY = baselineYAtX(row, boxCenterX(box));
  const touchesBaselineZone = box.top <= baselineY + 5 && boxBottom(box) >= baselineY - 7;
  const nearBaselineCenter = Math.abs(boxCenterY(box) - baselineY) <= Math.max(10, box.height * 0.75);
  return touchesBaselineZone || nearBaselineCenter;
}

function percentile(values: number[], q: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  const next = sorted[base + 1] ?? sorted[base];
  return sorted[base] + rest * (next - sorted[base]);
}

function rowTypicalWidth(baseComponents: RawComponent[]): { typicalWidth: number; narrowWidth: number } {
  const widths = baseComponents.map((component) => componentBox(component).width);
  let primary = widths.filter((width) => width >= 4 && width <= 32);
  if (primary.length < 5) primary = widths.filter((width) => width >= 3 && width <= 45);
  if (!primary.length) return { typicalWidth: 14, narrowWidth: 8 };
  return {
    typicalWidth: Math.max(6, percentile(primary, 0.5)),
    narrowWidth: Math.max(5, percentile(primary, 0.25)),
  };
}

function pointInPolygon(x: number, y: number, polygon: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i, i += 1) {
    const xi = polygon[i][0];
    const yi = polygon[i][1];
    const xj = polygon[j][0];
    const yj = polygon[j][1];
    const intersects = (yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-6) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

function componentMaskData(component: RawComponent, scale: number): MaskData | null {
  const polygon = component.polygon_scaled;
  if (!polygon || polygon.length < 3) return null;
  const xs = polygon.map((point) => point[0]);
  const ys = polygon.map((point) => point[1]);
  const left = Math.floor(Math.min(...xs));
  const top = Math.floor(Math.min(...ys));
  const right = Math.ceil(Math.max(...xs));
  const bottom = Math.ceil(Math.max(...ys));
  const width = Math.max(1, right - left + 1);
  const height = Math.max(1, bottom - top + 1);
  const mask = new Uint8Array(width * height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (pointInPolygon(left + x + 0.5, top + y + 0.5, polygon)) {
        mask[y * width + x] = 1;
      }
    }
  }
  return { mask, width, height, originScaled: [left, top], scale };
}

function maskColumnCounts(data: MaskData): number[] {
  const counts = new Array<number>(data.width).fill(0);
  for (let y = 0; y < data.height; y += 1) {
    const offset = y * data.width;
    for (let x = 0; x < data.width; x += 1) {
      if (data.mask[offset + x]) counts[x] += 1;
    }
  }
  return counts;
}

function cutCandidates(data: MaskData, targetCount: number, typicalWidth: number, narrowWidth: number): { cuts: number[]; method: string } {
  if (targetCount < 2 || data.width < 4) return { cuts: [], method: "no_split_needed" };
  const columnCounts = maskColumnCounts(data);
  const maxCount = Math.max(...columnCounts);
  if (maxCount <= 0) return { cuts: [], method: "empty_mask" };
  const positive = columnCounts.filter((count) => count > 0);
  const typicalInk = positive.length ? percentile(positive, 0.7) : 1;
  const lowThreshold = Math.max(1, typicalInk * 0.22);
  const minChild = Math.max(3, Math.round(narrowWidth * data.scale * 0.45));
  const searchRadius = Math.max(5, Math.round(typicalWidth * data.scale * 0.8));
  const idealPositions = Array.from({ length: targetCount - 1 }, (_unused, index) => data.width * (index + 1) / targetCount);
  const candidates: { center: number; depth: number; priority: number; score?: number }[] = [];

  let inLowRegion = false;
  let startCol = 0;
  for (let columnIndex = 0; columnIndex < columnCounts.length; columnIndex += 1) {
    const value = columnCounts[columnIndex];
    if (value <= lowThreshold) {
      if (!inLowRegion) {
        startCol = columnIndex;
        inLowRegion = true;
      }
    } else if (inLowRegion) {
      const endCol = columnIndex - 1;
      inLowRegion = false;
      if (startCol > minChild && endCol < data.width - minChild && endCol - startCol + 1 >= 2) {
        const region = columnCounts.slice(startCol, endCol + 1);
        candidates.push({ center: Math.round((startCol + endCol) / 2), depth: percentile(region, 0.5), priority: 0 });
      }
    }
  }
  if (inLowRegion) {
    const endCol = data.width - 1;
    if (startCol > minChild && endCol < data.width - minChild && endCol - startCol + 1 >= 2) {
      const region = columnCounts.slice(startCol, endCol + 1);
      candidates.push({ center: Math.round((startCol + endCol) / 2), depth: percentile(region, 0.5), priority: 0 });
    }
  }

  if (candidates.length < targetCount - 1) {
    const smooth = columnCounts.map((value, index) => {
      const left = columnCounts[index - 1] ?? value;
      const right = columnCounts[index + 1] ?? value;
      return (left + value + right) / 3;
    });
    for (let columnIndex = minChild; columnIndex < data.width - minChild; columnIndex += 1) {
      if (smooth[columnIndex] <= smooth[columnIndex - 1] && smooth[columnIndex] <= smooth[columnIndex + 1]) {
        if (candidates.some((candidate) => Math.abs(candidate.center - columnIndex) <= 2)) continue;
        candidates.push({ center: columnIndex, depth: smooth[columnIndex], priority: 1 });
      }
    }
  }
  if (!candidates.length) return { cuts: [], method: "no_cut_candidates" };

  const accepted: typeof candidates = [];
  for (const ideal of idealPositions) {
    const nearby = candidates.filter((candidate) => (
      Math.abs(candidate.center - ideal) <= searchRadius &&
      accepted.every((old) => Math.abs(candidate.center - old.center) >= minChild)
    ));
    if (!nearby.length) continue;
    for (const candidate of nearby) {
      const depthNorm = candidate.depth / Math.max(1, typicalInk);
      const distanceNorm = Math.abs(candidate.center - ideal) / Math.max(1, typicalWidth * data.scale);
      candidate.score = depthNorm + 0.55 * distanceNorm;
    }
    accepted.push(nearby.sort((a, b) => a.priority - b.priority || (a.score ?? 0) - (b.score ?? 0))[0]);
  }

  const cuts = accepted.map((item) => item.center).sort((a, b) => a - b);
  if (cuts.length === targetCount - 1 && accepted.every((item) => item.priority === 0)) {
    return { cuts, method: "strong_low_ink_projection" };
  }
  if (cuts.length) return { cuts, method: "usable_projection_minima" };
  return { cuts: [], method: "no_near_ideal_cuts" };
}

function bboxFromSegment(data: MaskData, leftCol: number, rightCol: number): Box | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (let y = 0; y < data.height; y += 1) {
    for (let x = leftCol; x < rightCol; x += 1) {
      if (!data.mask[y * data.width + x]) continue;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  if (!Number.isFinite(minX)) return null;
  return {
    left: (data.originScaled[0] + minX) / data.scale,
    top: (data.originScaled[1] + minY) / data.scale,
    width: (maxX - minX + 1) / data.scale,
    height: (maxY - minY + 1) / data.scale,
  };
}

function splitBaseComponent(
  component: RawComponent,
  row: RawGeometryRow,
  page: string,
  typicalWidth: number,
  narrowWidth: number,
  scale: number,
): LineEditorBox[] {
  const sourceBox = componentBox(component);
  const splitThreshold = Math.max(typicalWidth * 1.55, narrowWidth * 2, 18);
  const targetCount = Math.max(1, Math.min(5, Math.round(sourceBox.width / Math.max(typicalWidth, 1))));
  const mayBeConnected = sourceBox.width >= splitThreshold;
  const baseId = `proposal_p${page}_r${String(row.index).padStart(3, "0")}_c${String(component.id).padStart(5, "0")}`;

  if (targetCount < 2 || !mayBeConnected) {
    return [{
      id: baseId,
      ...xyxyToFields(boxToXyxy(sourceBox)),
      label: null,
      source: "proposal",
      source_component_ids: [component.id],
      split_method: "component_intact",
      confidence: "usable",
      kind: "base",
      include: true,
    }];
  }

  const maskData = componentMaskData(component, scale);
  if (!maskData) {
    return [{
      id: baseId,
      ...xyxyToFields(boxToXyxy(sourceBox)),
      label: null,
      source: "proposal",
      source_component_ids: [component.id],
      split_method: "component_intact_no_mask",
      confidence: "needs_review",
      kind: "base",
      include: true,
    }];
  }
  const { cuts, method } = cutCandidates(maskData, targetCount, typicalWidth, narrowWidth);
  if (!cuts.length) {
    return [{
      id: baseId,
      ...xyxyToFields(boxToXyxy(sourceBox)),
      label: null,
      source: "proposal",
      source_component_ids: [component.id],
      split_method: "component_intact_connected_candidate",
      confidence: "needs_review",
      kind: "base",
      include: true,
    }];
  }
  const boundaries = [0, ...cuts, maskData.width];
  const boxes: LineEditorBox[] = [];
  for (let index = 0; index < boundaries.length - 1; index += 1) {
    const child = bboxFromSegment(maskData, boundaries[index], boundaries[index + 1]);
    if (!child) continue;
    boxes.push({
      id: `${baseId}_s${index + 1}`,
      ...xyxyToFields(boxToXyxy(child)),
      label: null,
      source: "proposal",
      source_component_ids: [component.id],
      split_method: method,
      confidence: method === "strong_low_ink_projection" ? "strong" : "usable",
      kind: "base",
      include: true,
    });
  }
  return boxes.length ? boxes : [{
    id: baseId,
    ...xyxyToFields(boxToXyxy(sourceBox)),
    label: null,
    source: "proposal",
    source_component_ids: [component.id],
    split_method: "component_intact_split_empty",
    confidence: "needs_review",
    kind: "base",
    include: true,
  }];
}

function xyxyToFields([x0, y0, x1, y1]: [number, number, number, number]) {
  return { x0, y0, x1, y1 };
}

function componentKind(component: RawComponent, row: RawGeometryRow): LineEditorComponent["kind"] {
  if (componentIsExcluded(component)) return "excluded";
  if (isDotMark(component)) return "dot";
  if (isHorizontalMark(component)) return "horizontal";
  if (isBaseComponent(component, row)) return "base";
  return "other";
}

function existingToBox(row: NewBboxRow): LineEditorBox {
  const label = row.label;
  const kind = row.kind === "lacuna_dot" || row.kind === "mark"
    ? row.kind
    : label === "." || label === "_lacuna_dot" ? "lacuna_dot" : "base";
  return {
    id: row.id,
    x0: row.x0,
    y0: row.y0,
    x1: row.x1,
    y1: row.y1,
    label,
    source: "existing",
    source_component_ids: [],
    split_method: "manual_new_bbox",
    confidence: "usable",
    kind,
    include: true,
  };
}

async function readRawGeometry(page: string): Promise<RawGeometryPage> {
  const filePath = geometryPath(page);
  const text = await fsPromises.readFile(filePath, "utf8");
  return JSON.parse(text) as RawGeometryPage;
}

function templateInfos(): LineEditorTemplateInfo[] {
  if (!fs.existsSync(TEMPLATE_DIR)) return [];
  return fs.readdirSync(TEMPLATE_DIR)
    .filter((name) => name.endsWith("_line_profile_family.json"))
    .map((name) => {
      try {
        const data = JSON.parse(fs.readFileSync(path.join(TEMPLATE_DIR, name), "utf8")) as Record<string, unknown>;
        return {
          label: String(data.label ?? ""),
          label_slug: String(data.label_slug ?? name.replace(/_line_profile_family\.json$/, "")),
          sample_count: typeof data.sample_count === "number" ? data.sample_count : null,
        };
      } catch {
        return null;
      }
    })
    .filter((item): item is LineEditorTemplateInfo => Boolean(item?.label))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export async function buildLineEditorPayload(
  page: string,
  lineIndex: number,
  existingNewBboxes: NewBboxRow[],
): Promise<LineEditorPayload | null> {
  const pageInt = parseInt(page, 10);
  if (!Number.isFinite(pageInt)) return null;
  const raw = await readRawGeometry(page);
  const layout = buildCanonicalLineLayout(raw.geometry_rows);
  const canonicalLineIndex = canonicalizeLineIndex(layout, lineIndex);
  const canonicalRow = layout?.rows.find((row) => row.index === canonicalLineIndex);
  const sourceIndices = sourceIndicesForCanonicalLine(layout, canonicalLineIndex);
  const rowByIndex = new Map(raw.geometry_rows.map((row) => [row.index, row]));
  const primaryRow = sourceIndices
    .map((index) => rowByIndex.get(index))
    .find((row): row is RawGeometryRow => Boolean(row))
    ?? rowByIndex.get(canonicalLineIndex)
    ?? raw.geometry_rows[0];
  if (!primaryRow || !canonicalRow) return null;

  const componentRecords: LineEditorComponent[] = [];
  const proposals: LineEditorBox[] = [];
  const rowBbox = boxFromValues(canonicalRow.bbox);
  const previewBbox = expandBox(
    rowBbox,
    LINE_EDITOR_PREVIEW_PAD_X,
    LINE_EDITOR_PREVIEW_PAD_Y,
    raw.image_size,
  );
  const proposalScanBbox: Box = {
    left: previewBbox.left,
    top: rowBbox.top,
    width: previewBbox.width,
    height: rowBbox.height,
  };
  const previewComponents = raw.components
    .filter((component) => boxesIntersect(componentBox(component), proposalScanBbox))
    .sort((a, b) => componentBox(a).left - componentBox(b).left || componentBox(a).top - componentBox(b).top);
  const baseComponents = previewComponents.filter((component) => isBaseComponent(component, primaryRow));
  const { typicalWidth, narrowWidth } = rowTypicalWidth(baseComponents);

  for (const component of previewComponents) {
    const box = componentBox(component);
    const area = component.area_px ?? 0;
    if (box.width < 2 || box.height < 3 || area < 4) continue;
    componentRecords.push({
      id: component.id,
      bbox: component.bbox,
      kind: componentKind(component, primaryRow),
      area_px: round2(area),
    });
    if (isBaseComponent(component, primaryRow)) {
      proposals.push(...splitBaseComponent(component, primaryRow, page, typicalWidth, narrowWidth, raw.scale ?? 2));
    } else if (isLacunaDotCharacter(component)) {
      proposals.push({
        id: `dot_p${page}_preview_c${String(component.id).padStart(5, "0")}`,
        ...xyxyToFields(boxToXyxy(box)),
        label: ".",
        source: "proposal",
        source_component_ids: [component.id],
        split_method: "preview_lacuna_dot",
        confidence: "usable",
        kind: "lacuna_dot",
        include: true,
      });
    } else if (isDotMark(component) || isHorizontalMark(component)) {
      proposals.push({
        id: `mark_p${page}_preview_c${String(component.id).padStart(5, "0")}`,
        ...xyxyToFields(boxToXyxy(box)),
        label: null,
        source: "proposal",
        source_component_ids: [component.id],
        split_method: "preview_mark",
        confidence: "reference",
        kind: "mark",
        include: false,
      });
    } else {
      proposals.push({
        id: `other_p${page}_preview_c${String(component.id).padStart(5, "0")}`,
        ...xyxyToFields(boxToXyxy(box)),
        label: null,
        source: "proposal",
        source_component_ids: [component.id],
        split_method: "preview_component",
        confidence: "needs_review",
        kind: "base",
        include: true,
      });
    }
  }

  const existing = existingNewBboxes
    .filter((row) => canonicalizeLineIndex(layout, row.line_index) === canonicalLineIndex)
    .map((row) => existingToBox({
      ...row,
      line_index: canonicalizeLineIndex(layout, row.line_index),
    }));

  return {
    page,
    page_int: pageInt,
    line_index: canonicalLineIndex,
    display_index: canonicalRow.display_index,
    source_indices: sourceIndices,
    image_size: raw.image_size,
    image_url: `/api/image?root=textbody&p=${encodeURIComponent(`p${page}_text_body.jpg`)}`,
    row_bbox: [rowBbox.left, rowBbox.top, rowBbox.width, rowBbox.height],
    components: componentRecords.sort((a, b) => a.bbox[0] - b.bbox[0]),
    proposals: proposals.sort((a, b) => a.x0 - b.x0 || a.y0 - b.y0),
    existing_bboxes: existing,
    templates: templateInfos(),
  };
}