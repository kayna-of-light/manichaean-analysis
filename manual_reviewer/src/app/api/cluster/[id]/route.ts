import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { PIPELINE } from "@/lib/paths";
import {
  applyClusterOverride,
  readClusterOverride,
  unsetBlob,
} from "@/lib/repo";
import { z } from "zod";

export const dynamic = "force-dynamic";

interface AssignmentRow {
  page: string;
  line_index: number;
  blob_id: number;
  warped_bbox: [number, number, number, number];
  area: number;
  cluster: number;
  distance: number;
}

// One-shot in-memory index: cluster -> rows. Streamed once.
let _byCluster: Map<number, AssignmentRow[]> | null = null;

async function loadAssignments(): Promise<Map<number, AssignmentRow[]>> {
  if (_byCluster) return _byCluster;
  const m = new Map<number, AssignmentRow[]>();
  const file = PIPELINE.clusterAssignments;
  if (!fs.existsSync(file)) {
    _byCluster = m;
    return m;
  }
  const txt = await fs.promises.readFile(file, "utf8");
  // The file is a single JSON array (formatted with newlines).
  const arr = JSON.parse(txt) as AssignmentRow[];
  for (const row of arr) {
    const list = m.get(row.cluster) ?? [];
    list.push(row);
    m.set(row.cluster, list);
  }
  _byCluster = m;
  return m;
}

const QuerySchema = z.object({
  limit: z.coerce.number().min(1).max(2000).default(120),
  offset: z.coerce.number().min(0).default(0),
});

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

  const map = await loadAssignments();
  const all = map.get(cid) ?? [];
  // sort by distance ascending (closest to centroid first)
  const sorted = [...all].sort((a, b) => a.distance - b.distance);
  const slice = sorted.slice(q.offset, q.offset + q.limit);

  // Cluster thumbnails (cluster-centroid renderings; pre-rendered by pipeline)
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
    total: all.length,
    offset: q.offset,
    limit: q.limit,
    members: slice.map((r) => ({
      page: r.page,
      line_index: r.line_index,
      blob_id: r.blob_id,
      warped_bbox: r.warped_bbox,
      area: r.area,
      distance: r.distance,
    })),
    thumbs,
    override,
    thumb_dir: path.basename(dir),
  });
}

const POSTSchema = z.object({
  action: z.enum(["apply_label", "unset_blobs", "clear"]),
  label: z.string().nullable().optional(),
  diacritics: z.array(z.string()).nullable().optional(),
  note: z.string().nullable().optional(),
  members: z
    .array(
      z.object({
        page: z.string(),
        line_index: z.number(),
        blob_id: z.number(),
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
  return NextResponse.json({ error: "unsupported action" }, { status: 400 });
}
