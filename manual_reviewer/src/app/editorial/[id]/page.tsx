import { EditorialSentenceClient } from "./EditorialSentenceClient";

export const dynamic = "force-dynamic";

export default async function EditorialSentencePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const sentenceId = parseInt(id, 10);
  if (!Number.isFinite(sentenceId)) {
    return <div style={{ padding: 24 }}>Invalid sentence id.</div>;
  }
  return <EditorialSentenceClient sentenceId={sentenceId} />;
}
