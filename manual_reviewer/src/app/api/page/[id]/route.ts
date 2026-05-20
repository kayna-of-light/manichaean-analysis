import { NextRequest, NextResponse } from "next/server";
import {
  readInitialBaseline,
  readV2Geometry,
  textBodyImageUrl,
} from "@/lib/pipelineReaders";
import { buildEditorialOverlayForPage } from "@/lib/editorial";
import {
  mergeTokens,
  readBlobEdits,
  readClusterOverridesByIds,
  readLineStatuses,
  readNewBboxes,
  readReassignmentsForPage,
} from "@/lib/repo";
import type { BaselineLine, BaselineToken, Token } from "@/lib/zodSchemas";
import { getDb } from "@/lib/db";
import { editIdsForBaselineLine } from "@/lib/tokenIdentity";

export const dynamic = "force-dynamic";

/**
 * v2 canvas / v1 baseline. The image is the v2 text_body crop. Line geometry
 * comes from v2 body_geometry baselines; token positions are v1 img_quads
 * remapped into v2 text_body coordinates by the offline transposer
 * (scripts/projects/manual_reviewer_ingest/transpose_v1_to_v2.py).
 *
 * Editing layers (blob_edits / cluster_overrides / new_bboxes / unset_blobs /
 * line statuses) are unchanged — overrides on top of the baseline tokens,
 * keyed by (page, line_index, edit_id). edit_id is the source blob_id unless
 * that id appears multiple times on the same line, in which case it receives
 * a stable occurrence suffix so edits target one rendered box.
 */
export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const page = id.padStart(3, "0");
  const pageInt = parseInt(page, 10);
  if (!Number.isFinite(pageInt)) {
    return NextResponse.json({ error: "invalid page id" }, { status: 400 });
  }

  const baseline = await readInitialBaseline(page);
  if (!baseline) {
    return NextResponse.json({ error: "page not found" }, { status: 404 });
  }

  // v2 geometry provides actual ink bounding boxes per row — much better for
  // line strip cropping than deriving from baseline_y.
  // bbox format is [x, y, width, height] — convert to [x0, y0, x1, y1].
  const v2Rows = await readV2Geometry(page);
  const rowBboxMap = new Map<number, [number, number, number, number]>();
  if (v2Rows) {
    for (const r of v2Rows) {
      const [bx, by, bw, bh] = r.bbox;
      rowBboxMap.set(r.index, [bx, by, bx + bw, by + bh]);
    }
  }

  const baselineYs = baseline.lines.map((l) => l.baseline_y).sort((a, b) => a - b);
  const steps: number[] = [];
  for (let i = 1; i < baselineYs.length; i++) steps.push(baselineYs[i] - baselineYs[i - 1]);
  steps.sort((a, b) => a - b);
  const medianStep = steps.length > 0 ? steps[Math.floor(steps.length / 2)] : 40;
  const halfStep = Math.max(medianStep / 2, 12);

  const clusterIds = new Set<number>();
  for (const ln of baseline.lines) {
    for (const t of ln.tokens) {
      const cid = parseInt(t.cluster, 10);
      if (Number.isFinite(cid)) clusterIds.add(cid);
    }
  }

  const edits = readBlobEdits(pageInt);
  const reassignments = readReassignmentsForPage(pageInt);
  for (const r of reassignments.values()) clusterIds.add(r.to_cluster);
  const clusterOverrides = readClusterOverridesByIds([...clusterIds]);
  const newBboxes = readNewBboxes(pageInt);
  const parsedNewBboxes = newBboxes.map((nb) => ({
    ...nb,
    diacritics: parseDiacritics(nb.diacritics),
  }));
  const lineStatuses = readLineStatuses(pageInt);

  const db = getDb();
  const unsetRows = db
    .prepare<[number], { line_index: number; blob_id: string }>(
      "SELECT line_index, blob_id FROM unset_blobs WHERE page = ?",
    )
    .all(pageInt);
  const unsetSet = new Set(unsetRows.map((r) => `${r.line_index}:${r.blob_id}`));
  const editorialOverlays = await buildEditorialOverlayForPage(
    page,
    baseline,
    unsetSet,
    reassignments,
  );

  const [imgW, imgH] = baseline.image_size;
  const builtLines = baseline.lines.map((ln) =>
    buildLine(ln, page, halfStep, imgW, imgH, rowBboxMap),
  );

  const mergedLines = builtLines.map((ln) => {
    const tokens = mergeTokens(
      pageInt,
      ln.tokens,
      edits,
      clusterOverrides,
      unsetSet,
      reassignments,
      editorialOverlays,
    );
    const tokensWithQuad = tokens.map((t, idx) => ({
      ...t,
      img_quad: ln.quads[idx],
    }));
    const status = lineStatuses.get(ln.line_index) ?? {
      status: "pending" as const,
      note: null,
    };
    return {
      line_index: ln.line_index,
      tokens: tokensWithQuad,
      warped_size: ln.warped_size,
      line_quad: ln.line_quad,
      status: status.status,
      note: status.note,
    };
  });

  return NextResponse.json({
    page,
    page_int: pageInt,
    image_size: [imgW, imgH] as [number, number],
    page_size: [imgW, imgH] as [number, number],
    bbox: { x0: 0, y0: 0, x1: imgW, y1: imgH },
    baseline_y_warped: 0,
    warp_height: 0,
    image_url: textBodyImageUrl(page),
    lines: mergedLines,
    new_bboxes: parsedNewBboxes,
    baseline_meta: {
      rows_v1: baseline.rows_v1 ?? null,
      rows_v2: baseline.rows_v2 ?? null,
      rows_aligned: baseline.rows_aligned ?? null,
      tokens_excluded: baseline.tokens_excluded ?? null,
    },
  });
}

function parseDiacritics(value: string | null): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

function buildLine(
  ln: BaselineLine,
  page: string,
  halfStep: number,
  imgW: number,
  imgH: number,
  rowBboxMap: Map<number, [number, number, number, number]>,
) {
  const editIds = editIdsForBaselineLine(ln);
  const allTokens: Token[] = ln.tokens.map((t, index) =>
    baselineTokenToToken(t, page, ln.line_index, editIds[index]),
  );
  const allQuads: (number[][] | null)[] = ln.tokens.map((t) => t.geometry.img_quad);

  // Use a stable page-wide x-frame for every strip. If each row crops to its
  // own ink width, short rows are magnified much more than long rows and the
  // reviewer feels like boxes drift when scrolling between lines.
  const LINE_MARGIN_Y = 6;
  const rowBbox = rowBboxMap.get(ln.line_index);
  const quadBounds = boundsForQuads(allQuads);
  let x0: number, x1: number, yTop: number, yBot: number;
  x0 = 0;
  x1 = imgW;
  if (rowBbox) {
    yTop = Math.max(0, rowBbox[1] - LINE_MARGIN_Y);
    yBot = Math.min(imgH, rowBbox[3] + LINE_MARGIN_Y);
    if (quadBounds) {
      yTop = Math.max(0, Math.min(yTop, quadBounds[1] - LINE_MARGIN_Y));
      yBot = Math.min(imgH, Math.max(yBot, quadBounds[3] + LINE_MARGIN_Y));
    }
  } else {
    const step = halfStep * 2;
    yTop = ln.baseline_y - step * 0.85;
    yBot = ln.baseline_y + step * 0.15;
  }

  const line_quad: number[][] = [
    [x0, yTop],
    [x1, yTop],
    [x1, yBot],
    [x0, yBot],
  ];
  const warped_size: [number, number] = [
    Math.max(x1 - x0, 1),
    Math.max(yBot - yTop, 1),
  ];
  return { line_index: ln.line_index, tokens: allTokens, quads: allQuads, line_quad, warped_size };
}

function boundsForQuads(quads: (number[][] | null)[]): [number, number, number, number] | null {
  const xs: number[] = [];
  const ys: number[] = [];
  for (const quad of quads) {
    if (!quad) continue;
    for (const point of quad) {
      xs.push(point[0]);
      ys.push(point[1]);
    }
  }
  if (xs.length === 0 || ys.length === 0) return null;
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

function baselineTokenToToken(
  t: BaselineToken,
  page: string,
  line_index: number,
  edit_id: string,
): Token {
  const [ax0, ay0, ax1, ay1] = t.geometry.aabb;
  const width = ax1 - ax0;
  const height = ay1 - ay0;
  const area = width * height;
  return {
    page,
    line_index,
    v1_line_index: t.v1_line_index,
    blob_id: t.blob_id,
    edit_id,
    cluster: t.cluster,
    label: t.label ?? null,
    manual_override: t.manual_override ?? null,
    manual_warning: t.manual_warning ?? null,
    subcluster_override: t.subcluster_override ?? null,
    geometric_override: t.geometric_override ?? null,
    editorial_override: t.editorial_override ?? null,
    review: t.review ?? false,
    candidates: t.candidates ?? [],
    overline_mark_id: t.overline_mark_id ?? null,
    geometry: {
      warped_bbox: t.geometry.warped_bbox,
      width,
      height,
      area,
      aspect: height > 0 ? width / height : 0,
      center_x: (ax0 + ax1) / 2,
      center_y: (ay0 + ay1) / 2,
    },
  };
}
