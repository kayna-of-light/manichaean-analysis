import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { PIPELINE } from "@/lib/paths";
import { readInitialBaseline, textBodyImageUrl } from "@/lib/pipelineReaders";
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
  limit: z.coerce.number().min(1).max(5000).default(500),
  offset: z.coerce.number().min(0).default(0),
});

interface EnrichedMember {
  page: string;
  line_index: number;
  blob_id: number;
  origin_cluster: number;
  reassigned: boolean;
  unset: boolean;
  warped_bbox: [number, number, number, number];
  area: number;
  distance: number | null;
  img_quad: [number, number][] | null;
  aabb: [number, number, number, number] | null;
  image_url: string;
  image_size: [number, number] | null;
}

async function enrich(
  page: string,
  line_index: number,
  blob_id: number,
  origin_cluster: number,
  reassigned: boolean,
  unset: boolean,
  warped_bbox: [number, number, number, number],
  area: number,
  distance: number | null,
): Promise<EnrichedMember> {
  const baseline = await readInitialBaseline(page);
  let img_quad: [number, number][] | null = null;
  let aabb: [number, number, number, number] | null = null;
  let image_size: [number, number] | null = null;
  if (baseline) {
    image_size = baseline.image_size;
    const ln = baseline.lines.find((l) => l.line_index === line_index);
    const tk = ln?.tokens.find((t) => t.blob_id === blob_id);
    if (tk) {
      img_quad = tk.geometry.img_quad as [number, number][];
      aabb = tk.geometry.aabb;
    }
  }
  return {
    page,
    line_index,
    blob_id,
    origin_cluster,
    reassigned,
    unset,
    warped_bbox,
    area,
    distance,
    img_quad,
    aabb,
    image_url: textBodyImageUrl(page),
    image_size,
  };
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

  const map = await loadAssignments();
  const original = map.get(cid) ?? [];
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
  type PresentRow = {
    page: string;
    line_index: number;
    blob_id: number;
    origin_cluster: number;
    reassigned: boolean;
    unset: boolean;
    warped_bbox: [number, number, number, number];
    area: number;
    distance: number | null;
  };
  const present = new Map<string, PresentRow>();

  for (const r of original) {
    const key = `${r.page}:${r.line_index}:${r.blob_id}`;
    if (reassignedAway.has(key)) continue;
    present.set(key, {
      page: r.page,
      line_index: r.line_index,
      blob_id: r.blob_id,
      origin_cluster: cid,
      reassigned: false,
      unset: unsetKey.has(key),
      warped_bbox: r.warped_bbox,
      area: r.area,
      distance: r.distance,
    });
  }

  // Look up reassigned-in rows' original assignment metadata.
  const assignByKey = new Map<string, AssignmentRow>();
  for (const list of map.values()) {
    for (const r of list) {
      assignByKey.set(`${r.page}:${r.line_index}:${r.blob_id}`, r);
    }
  }
  for (const r of reassignedIn) {
    const page = String(r.page).padStart(3, "0");
    const key = `${page}:${r.line_index}:${r.blob_id}`;
    const a = assignByKey.get(key);
    present.set(key, {
      page,
      line_index: r.line_index,
      blob_id: parseInt(r.blob_id, 10),
      origin_cluster: r.from_cluster ?? cid,
      reassigned: true,
      unset: unsetKey.has(key),
      warped_bbox: a?.warped_bbox ?? [0, 0, 0, 0],
      area: a?.area ?? 0,
      distance: a?.distance ?? null,
    });
  }

  // Sort: reassigned-in first, then by distance ascending.
  const sorted = [...present.values()].sort((a, b) => {
    if (a.reassigned !== b.reassigned) return a.reassigned ? -1 : 1;
    const da = a.distance ?? 1e9;
    const dbb = b.distance ?? 1e9;
    return da - dbb;
  });

  const total = sorted.length;
  const slice = sorted.slice(q.offset, q.offset + q.limit);
  const members: EnrichedMember[] = await Promise.all(
    slice.map((m) =>
      enrich(
        m.page,
        m.line_index,
        m.blob_id,
        m.origin_cluster,
        m.reassigned,
        m.unset,
        m.warped_bbox,
        m.area,
        m.distance,
      ),
    ),
  );

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
