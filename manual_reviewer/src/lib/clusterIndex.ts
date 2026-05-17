import { listPages, readInitialBaseline, textBodyImageUrl } from "@/lib/pipelineReaders";
import type { BaselineToken } from "@/lib/zodSchemas";

export interface ClusterMemberCore {
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

export interface BaselineClusterIndex {
  byCluster: Map<number, ClusterMemberCore[]>;
  byKey: Map<string, ClusterMemberCore>;
}

export function memberKey(
  page: string,
  lineIndex: number,
  blobId: string | number,
): string {
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
): ClusterMemberCore | null {
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

// Module-level memoisation. Baseline JSONs never change at runtime, so a
// per-process cache keeps cluster routes cheap once the first request has
// warmed the index.
let cachedIndex: Promise<BaselineClusterIndex> | null = null;

async function buildIndex(): Promise<BaselineClusterIndex> {
  const byCluster = new Map<number, ClusterMemberCore[]>();
  const byKey = new Map<string, ClusterMemberCore>();
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

export function loadBaselineClusterIndex(): Promise<BaselineClusterIndex> {
  if (!cachedIndex) cachedIndex = buildIndex();
  return cachedIndex;
}
