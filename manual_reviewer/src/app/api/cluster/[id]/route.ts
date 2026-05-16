import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { PIPELINE } from "@/lib/paths";
import { listPages, readInitialBaseline, textBodyImageUrl } from "@/lib/pipelineReaders";
import {
  applyClusterOverride,
  clearReassignment,
  reassignBlob,
  readClusterOverride,
  readReassignmentsFromCluster,
  readReassignmentsToCluster,
  unsetBlob,
} from "@/lib/repo";
import { getDb } from "@/lib/db";
import type { BaselineToken } from "@/lib/zodSchemas";
import { z } from "zod";

export const dynamic = "force-dynamic";

const QuerySchema = z.object({
  limit: z.coerce.number().min(1).max(5000).default(500),
  offset: z.coerce.number().min(0).default(0),
});

interface EnrichedMember {
  page: string;
  line_index: number;
  source_line_index: number | null;
  blob_id: number;
  origin_cluster: number;
  reassigned: boolean;
  unset: boolean;
  label: string | null;
  warped_bbox: [number, number, number, number];
  area: number;
  distance: number | null;
  img_quad: [number, number][] | null;
  aabb: [number, number, number, number] | null;
  image_url: string;
  image_size: [number, number] | null;
}

interface BaselineClusterIndex {
  byCluster: Map<number, EnrichedMember[]>;
  byKey: Map<string, EnrichedMember>;
}

function memberKey(page: string, lineIndex: number, blobId: string | number) {
  return `${page}:${lineIndex}:${blobId}`;
}

function areaFromAabb(aabb: [number, number, number, number]): number {
  return Math.max(0, aabb[2] - aabb[0]) * Math.max(0, aabb[3] - aabb[1]);
}

function memberFromBaselineToken(
  page: string,
  lineIndex: number,
  sourceLineIndex: number | null,
  imageSize: [number, number],
  token: BaselineToken,
): EnrichedMember | null {
  const originCluster = parseInt(token.cluster, 10);
  if (!Number.isFinite(originCluster)) return null;
  const aabb = token.geometry.aabb;
  return {
    page,
    line_index: lineIndex,
    source_line_index: sourceLineIndex,
    blob_id: token.blob_id,
    origin_cluster: originCluster,
    reassigned: false,
    unset: false,
    label: token.label ?? null,
    warped_bbox: token.geometry.warped_bbox,
    area: areaFromAabb(aabb),
    distance: null,
    img_quad: token.geometry.img_quad,
    aabb,
    image_url: textBodyImageUrl(page),
    image_size: imageSize,
  };
}

async function loadBaselineClusterIndex(): Promise<BaselineClusterIndex> {
  const byCluster = new Map<number, EnrichedMember[]>();
  const byKey = new Map<string, EnrichedMember>();
  const pages = await listPages();
  for (const page of pages) {
    const baseline = await readInitialBaseline(page);
    if (!baseline) continue;
    for (const line of baseline.lines) {
      const sourceLineIndex = line.v1_line_index ?? null;
      for (const token of line.tokens) {
        const member = memberFromBaselineToken(
          page,
          line.line_index,
          sourceLineIndex,
          baseline.image_size,
          token,
        );
        if (!member) continue;
        byKey.set(memberKey(member.page, member.line_index, member.blob_id), member);
        const bucket = byCluster.get(member.origin_cluster) ?? [];
        bucket.push(member);
        byCluster.set(member.origin_cluster, bucket);
      }
    }
  }
  return { byCluster, byKey };
}

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const cid = parseInt(id, 10);
  if (!Number.isFinite(cid)) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  const { searchParams } = new URL(req.url);
  const q = QuerySchema.parse({
    limit: searchParams.get("limit"),
    offset: searchParams.get("offset"),
  });

  const baselineIndex = await loadBaselineClusterIndex();
  const original = baselineIndex.byCluster.get(cid) ?? [];
  const reassignedAway = readReassignmentsFromCluster(cid); // page:line:blob → row
  const reassignedIn = readReassignmentsToCluster(cid);

  const db = getDb();
  const unsetRows = db
    .prepare<[], { page: number; line_index: number; blob_id: string }>(
      "SELECT page, line_index, blob_id FROM unset_blobs",
    )
    .all();
  const unsetKey = new Set<string>(
    unsetRows.map(
      (r) => `${String(r.page).padStart(3, "0")}:${r.line_index}:${r.blob_id}`,
    ),
  );

  // Effective members = original − reassignedAway − unset + reassignedIn
  const present = new Map<string, EnrichedMember>();

  for (const r of original) {
    const key = memberKey(r.page, r.line_index, r.blob_id);
    if (reassignedAway.has(key)) continue;
    if (unsetKey.has(key)) continue;
    present.set(key, r);
  }

  for (const r of reassignedIn) {
    const page = String(r.page).padStart(3, "0");
    const key = memberKey(page, r.line_index, r.blob_id);
    if (unsetKey.has(key)) continue;
    const member = baselineIndex.byKey.get(key);
    if (!member) continue;
    present.set(key, {
      ...member,
      origin_cluster: r.from_cluster ?? cid,
      reassigned: true,
      unset: false,
    });
  }

  // Sort: reassigned-in first, then page/line/position for predictable review.
  const sorted = [...present.values()].sort((a, b) => {
    if (a.reassigned !== b.reassigned) return a.reassigned ? -1 : 1;
    if (a.page !== b.page) return a.page.localeCompare(b.page);
    if (a.line_index !== b.line_index) return a.line_index - b.line_index;
    const ax = a.aabb?.[0] ?? 0;
    const bx = b.aabb?.[0] ?? 0;
    return ax - bx;
  });

  const total = sorted.length;
  const members = sorted.slice(q.offset, q.offset + q.limit);

  // Cluster centroid thumbnails (pre-rendered by pipeline)
  const padded = String(cid).padStart(3, "0");
  const dir = PIPELINE.clusters;
  const thumbs = fs.existsSync(dir)
    ? fs
        .readdirSync(dir)
        .filter((f) => f.startsWith(`c_${padded}_`) && f.endsWith(".png"))
        .map((f) => `/api/image?root=clusters&p=${encodeURIComponent(f)}`)
    : [];

  const override = readClusterOverride(cid);
  return NextResponse.json({
    cluster_id: cid,
    total,
    original_total: original.length,
    reassigned_in: reassignedIn.length,
    reassigned_away: reassignedAway.size,
    offset: q.offset,
    limit: q.limit,
    members,
    thumbs,
    override,
    thumb_dir: path.basename(dir),
  });
}

const POSTSchema = z.object({
  action: z.enum([
    "apply_label",
    "unset_blobs",
    "reassign_blobs",
    "clear_reassignments",
    "clear",
  ]),
  label: z.string().nullable().optional(),
  diacritics: z.array(z.string()).nullable().optional(),
  note: z.string().nullable().optional(),
  to_cluster: z.number().int().nullable().optional(),
  members: z
    .array(
      z.object({
        page: z.string(),
        line_index: z.number(),
        blob_id: z.number(),
        from_cluster: z.number().int().nullable().optional(),
      }),
    )
    .optional(),
});

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const cid = parseInt(id, 10);
  if (!Number.isFinite(cid)) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  let body: z.infer<typeof POSTSchema>;
  try {
    body = POSTSchema.parse(await req.json());
  } catch (err) {
    return NextResponse.json(
      { error: "bad request", detail: (err as Error).message },
      { status: 400 },
    );
  }

  if (body.action === "apply_label") {
    const after = applyClusterOverride(
      cid,
      body.label ?? null,
      body.diacritics ?? null,
      body.note ?? null,
    );
    return NextResponse.json({ ok: true, override: after });
  }
  if (body.action === "clear") {
    const after = applyClusterOverride(cid, null, null, body.note ?? null);
    return NextResponse.json({ ok: true, override: after });
  }
  if (body.action === "unset_blobs") {
    const members = body.members ?? [];
    for (const m of members) {
      unsetBlob(parseInt(m.page, 10), m.line_index, String(m.blob_id), cid);
    }
    return NextResponse.json({ ok: true, unset_count: members.length });
  }
  if (body.action === "reassign_blobs") {
    if (body.to_cluster == null || !Number.isFinite(body.to_cluster)) {
      return NextResponse.json(
        { error: "to_cluster required" },
        { status: 400 },
      );
    }
    const members = body.members ?? [];
    for (const m of members) {
      reassignBlob(
        parseInt(m.page, 10),
        m.line_index,
        String(m.blob_id),
        m.from_cluster ?? cid,
        body.to_cluster,
        body.note ?? null,
      );
    }
    return NextResponse.json({
      ok: true,
      reassigned_count: members.length,
      to_cluster: body.to_cluster,
    });
  }
  if (body.action === "clear_reassignments") {
    const members = body.members ?? [];
    let cleared = 0;
    for (const m of members) {
      const res = clearReassignment(
        parseInt(m.page, 10),
        m.line_index,
        String(m.blob_id),
      );
      if (res !== null) cleared += 1;
    }
    return NextResponse.json({ ok: true, cleared });
  }
  return NextResponse.json({ error: "unsupported action" }, { status: 400 });
}
