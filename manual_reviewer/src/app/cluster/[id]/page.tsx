import { ClusterPageClient } from "./ClusterPageClient";

export const dynamic = "force-dynamic";

export default async function ClusterPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const cid = parseInt(id, 10);
  if (!Number.isFinite(cid)) {
    return <div style={{ padding: 24 }}>Invalid cluster id.</div>;
  }
  return <ClusterPageClient clusterId={cid} />;
}
