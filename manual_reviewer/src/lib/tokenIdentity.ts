export function editIdsForBaselineLine(line: { tokens: Array<{ blob_id: number }> }): string[] {
  const totals = new Map<number, number>();
  for (const token of line.tokens) {
    totals.set(token.blob_id, (totals.get(token.blob_id) ?? 0) + 1);
  }

  const seen = new Map<number, number>();
  return line.tokens.map((token) => {
    const total = totals.get(token.blob_id) ?? 0;
    if (total <= 1) return String(token.blob_id);
    const occurrence = (seen.get(token.blob_id) ?? 0) + 1;
    seen.set(token.blob_id, occurrence);
    return `${token.blob_id}#${occurrence}`;
  });
}

export function editKey(lineIndex: number, editId: string | number): string {
  return `${lineIndex}:${editId}`;
}