import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import {
  loadBaselineClusterIndex,
  memberKey,
  type ClusterMemberCore,
} from "@/lib/clusterIndex";
import {
  applyClusterOverride,
  reassignBlob,
  readClusterOverridesByIds,
} from "@/lib/repo";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

interface ReassignmentRow {
  page: number;
  line_index: number;
  blob_id: string;
  from_cluster: number | null;
  to_cluster: number;
}

interface UnsetRow {
  page: number;
  line_index: number;
  blob_id: string;
}

function paddedPage(p: number): string {
  return String(p).padStart(3, "0");
}

interface ClusterSummary {
  cluster_id: number;
  active_count: number;
  baseline_count: number;
  override_label: string | null;
  sample_member: {
    page: string;
    line_index: number;
    blob_id: number;
    image_url: string;
    image_size: [number, number] | null;
    aabb: [number, number, number, number] | null;
  } | null;
}

/** Build the live (post-mutation) view of all clusters. */
async function buildClusterSummaries(): Promise<{
  clusters: ClusterSummary[];
  maxId: number;
}> {
  const index = await loadBaselineClusterIndex();
  const db = getDb();
  const reassignments = db
    .prepare<[], ReassignmentRow>(
      "SELECT page, line_index, blob_id, from_cluster, to_cluster FROM cluster_reassignments",
    )
    .all();
  const unsetRows = db
    .prepare<[], UnsetRow>(
      "SELECT page, line_index, blob_id FROM unset_blobs",
    )
    .all();
  const unsetKey = new Set<string>(
    unsetRows.map((r) => memberKey(paddedPage(r.page), r.line_index, r.blob_id)),
  );

  // Track effective membership per cluster id.
  const effective = new Map<number, ClusterMemberCore[]>();
  // Copy baseline (filtered by reassignAway + unset).
  const reassignAwayKey = new Map<string, ReassignmentRow>();
  for (const r of reassignments) {
    reassignAwayKey.set(memberKey(paddedPage(r.page), r.line_index, r.blob_id), r);
  }
  for (const [cid, members] of index.byCluster) {
    const bucket: ClusterMemberCore[] = [];
    for (const m of members) {
      const key = memberKey(m.page, m.line_index, m.blob_id);
      if (unsetKey.has(key)) continue;
      if (reassignAwayKey.has(key)) continue;
      bucket.push(m);
    }
    effective.set(cid, bucket);
  }
  for (const r of reassignments) {
    const key = memberKey(paddedPage(r.page), r.line_index, r.blob_id);
    if (unsetKey.has(key)) continue;
    const baseline = index.byKey.get(key);
    if (!baseline) continue;
    const bucket = effective.get(r.to_cluster) ?? [];
    bucket.push({ ...baseline, origin_cluster: r.from_cluster ?? baseline.origin_cluster, reassigned: true });
    effective.set(r.to_cluster, bucket);
  }

  const allIds = new Set<number>([
    ...effective.keys(),
    ...index.byCluster.keys(),
  ]);
  const overrideIds = db
    .prepare<[], { cluster_id: number }>(
      "SELECT cluster_id FROM cluster_overrides",
    )
    .all();
  for (const o of overrideIds) allIds.add(o.cluster_id);

  const overrides = readClusterOverridesByIds([...allIds]);
  const summaries: ClusterSummary[] = [];
  let maxId = 0;
  for (const cid of allIds) {
    if (cid > maxId) maxId = cid;
    const members = effective.get(cid) ?? [];
    const baseline = index.byCluster.get(cid) ?? [];
    // Pseudo-random sample by hashing cluster id for stable order.
    const sample = members[Math.abs(cid * 2654435761) % Math.max(1, members.length)] ?? members[0] ?? null;
    summaries.push({
      cluster_id: cid,
      active_count: members.length,
      baseline_count: baseline.length,
      override_label: overrides.get(cid)?.label ?? null,
      sample_member: sample
        ? {
            page: sample.page,
            line_index: sample.line_index,
            blob_id: sample.blob_id,
            image_url: sample.image_url,
            image_size: sample.image_size,
            aabb: sample.aabb,
          }
        : null,
    });
  }

  summaries.sort((a, b) => a.cluster_id - b.cluster_id);
  return { clusters: summaries, maxId };
}

export async function GET() {
  const { clusters, maxId } = await buildClusterSummaries();
  return NextResponse.json({ clusters, max_cluster_id: maxId });
}

const POSTSchema = z.object({
  action: z.literal("create_from_selection"),
  label: z.string().nullable().optional(),
  diacritics: z.array(z.string()).nullable().optional(),
  note: z.string().nullable().optional(),
  members: z
    .array(
      z.object({
        page: z.string(),
        line_index: z.number(),
        blob_id: z.number(),
        from_cluster: z.number().int().nullable().optional(),
      }),
    )
    .min(1),
});

export async function POST(req: NextRequest) {
  let body: z.infer<typeof POSTSchema>;
  try {
    body = POSTSchema.parse(await req.json());
  } catch (err) {
    return NextResponse.json(
      { error: "bad request", detail: (err as Error).message },
      { status: 400 },
    );
  }

  const { maxId } = await buildClusterSummaries();
  const newId = Math.max(1, maxId + 1);

  if (body.label) {
    applyClusterOverride(
      newId,
      body.label,
      body.diacritics ?? null,
      body.note ?? null,
    );
  }
  for (const m of body.members) {
    reassignBlob(
      parseInt(m.page, 10),
      m.line_index,
      String(m.blob_id),
      m.from_cluster ?? null,
      newId,
      body.note ?? null,
    );
  }

  return NextResponse.json({
    ok: true,
    new_cluster_id: newId,
    reassigned_count: body.members.length,
    label: body.label ?? null,
  });
}
