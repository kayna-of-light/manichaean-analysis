import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { listPages, readInitialBaseline } from "@/lib/pipelineReaders";

export const dynamic = "force-dynamic";

interface PageProgressRow {
  page: number;
  status: string;
  last_edited_at: string | null;
  done_lines: number;
  flagged_lines: number;
}

export async function GET() {
  const pages = await listPages();
  const db = getDb();

  const rows = db
    .prepare<[], PageProgressRow>(
      `SELECT
         p.page                                                AS page,
         p.status                                              AS status,
         p.last_edited_at                                      AS last_edited_at,
         COALESCE(SUM(CASE WHEN l.status = 'done' THEN 1 ELSE 0 END), 0)    AS done_lines,
         COALESCE(SUM(CASE WHEN l.status = 'flagged' THEN 1 ELSE 0 END), 0) AS flagged_lines
       FROM pages p LEFT JOIN lines l ON l.page = p.page
       GROUP BY p.page`,
    )
    .all();
  const byId = new Map(rows.map((r) => [r.page, r]));

  // Read total line counts from baseline files (cached per-process)
  const lineCounts = new Map<string, number>();
  await Promise.all(
    pages.map(async (p) => {
      const baseline = await readInitialBaseline(p);
      if (baseline) lineCounts.set(p, baseline.lines.length);
    }),
  );

  const items = pages.map((p) => {
    const pid = parseInt(p, 10);
    const row = byId.get(pid);
    return {
      page: p,
      pageInt: pid,
      status: row?.status ?? "pending",
      last_edited_at: row?.last_edited_at ?? null,
      done_lines: row?.done_lines ?? 0,
      flagged_lines: row?.flagged_lines ?? 0,
      total_lines: lineCounts.get(p) ?? 0,
    };
  });

  return NextResponse.json({ pages: items });
}
