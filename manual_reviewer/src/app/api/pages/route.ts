import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { listPages, readInitialBaseline } from "@/lib/pipelineReaders";

export const dynamic = "force-dynamic";

interface PageRow {
  page: number;
  status: string;
  last_edited_at: string | null;
}

interface LineProgressRow {
  page: number;
  line_index: number;
  status: string;
}

interface PageProgress {
  done_lines: number;
  flagged_lines: number;
}

export async function GET() {
  const pages = await listPages();
  const db = getDb();

  const rows = db
    .prepare<[], PageRow>(
      `SELECT
         p.page           AS page,
         p.status         AS status,
         p.last_edited_at AS last_edited_at
       FROM pages p`,
    )
    .all();
  const byId = new Map(rows.map((r) => [r.page, r]));

  const lineRows = db
    .prepare<[], LineProgressRow>(
      `SELECT page, line_index, status
       FROM lines
       WHERE status IN ('done', 'flagged')`,
    )
    .all();

  // Read total line counts from baseline files (cached per-process)
  const lineCounts = new Map<string, number>();
  await Promise.all(
    pages.map(async (p) => {
      const baseline = await readInitialBaseline(p);
      if (baseline) lineCounts.set(p, baseline.lines.length);
    }),
  );

  const progressByPage = new Map<number, PageProgress>();
  for (const line of lineRows) {
    const page = String(line.page).padStart(3, "0");
    const totalLines = lineCounts.get(page) ?? 0;
    if (line.line_index < 0 || line.line_index >= totalLines) continue;
    const progress = progressByPage.get(line.page) ?? {
      done_lines: 0,
      flagged_lines: 0,
    };
    if (line.status === "done") progress.done_lines += 1;
    if (line.status === "flagged") progress.flagged_lines += 1;
    progressByPage.set(line.page, progress);
  }

  const items = pages.map((p) => {
    const pid = parseInt(p, 10);
    const row = byId.get(pid);
    const progress = progressByPage.get(pid);
    return {
      page: p,
      pageInt: pid,
      status: row?.status ?? "pending",
      last_edited_at: row?.last_edited_at ?? null,
      done_lines: progress?.done_lines ?? 0,
      flagged_lines: progress?.flagged_lines ?? 0,
      total_lines: lineCounts.get(p) ?? 0,
    };
  });

  return NextResponse.json({ pages: items });
}
