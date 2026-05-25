import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { buildCanonicalLineLayout } from "@/lib/canonicalLines";
import { listPages, readInitialBaseline, readV2Geometry } from "@/lib/pipelineReaders";

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

interface LineDuplicateRow {
  page: number;
  line_index: number;
}

interface PageProgress {
  done_lines: number;
  flagged_lines: number;
  special_lines: number;
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
        WHERE status IN ('done', 'flagged', 'special')`,
    )
    .all();

  const duplicateRows = db
    .prepare<[], LineDuplicateRow>(
      `SELECT page, line_index
       FROM line_duplicates`,
    )
    .all();

  // v2 body geometry is the page-structure source of truth. Fall back to the
  // transposed baseline only for pages missing geometry artifacts.
  const lineCounts = new Map<string, number>();
  const lineIndexes = new Map<string, Set<number>>();
  const canonicalByPage = new Map<string, Map<number, number>>();
  await Promise.all(
    pages.map(async (p) => {
      const canonicalLayout = buildCanonicalLineLayout(await readV2Geometry(p));
      if (canonicalLayout) {
        lineCounts.set(p, canonicalLayout.rows.length);
        lineIndexes.set(p, canonicalLayout.lineIndexes);
        canonicalByPage.set(p, canonicalLayout.canonicalBySourceIndex);
        return;
      }

      const baseline = await readInitialBaseline(p);
      if (baseline) {
        lineCounts.set(p, baseline.lines.length);
        lineIndexes.set(
          p,
          new Set(baseline.lines.map((line) => line.line_index)),
        );
      }
    }),
  );

  const statusByPage = new Map<number, Map<number, string>>();
  for (const duplicate of duplicateRows) {
    const page = String(duplicate.page).padStart(3, "0");
    const indexes = lineIndexes.get(page) ?? new Set<number>();
    indexes.add(duplicate.line_index);
    lineIndexes.set(page, indexes);
    lineCounts.set(page, (lineCounts.get(page) ?? 0) + 1);
  }

  for (const line of lineRows) {
    const page = String(line.page).padStart(3, "0");
    const canonicalLineIndex = canonicalByPage.get(page)?.get(line.line_index) ?? line.line_index;
    if (!lineIndexes.get(page)?.has(canonicalLineIndex)) continue;
    const statuses = statusByPage.get(line.page) ?? new Map<number, string>();
    const existing = statuses.get(canonicalLineIndex);
    if (!existing || statusRank(line.status) > statusRank(existing)) {
      statuses.set(canonicalLineIndex, line.status);
    }
    statusByPage.set(line.page, statuses);
  }

  const progressByPage = new Map<number, PageProgress>();
  for (const [page, statuses] of statusByPage.entries()) {
    const progress: PageProgress = {
      done_lines: 0,
      flagged_lines: 0,
      special_lines: 0,
    };
    for (const status of statuses.values()) {
      if (status === "done") progress.done_lines += 1;
      if (status === "flagged") progress.flagged_lines += 1;
      if (status === "special") progress.special_lines += 1;
    }
    progressByPage.set(page, progress);
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
      special_lines: progress?.special_lines ?? 0,
      total_lines: lineCounts.get(p) ?? 0,
    };
  });

  return NextResponse.json({ pages: items });
}

function statusRank(status: string): number {
  if (status === "flagged") return 4;
  if (status === "special") return 3;
  if (status === "done") return 2;
  return 1;
}
