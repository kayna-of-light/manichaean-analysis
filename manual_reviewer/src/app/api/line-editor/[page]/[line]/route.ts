import { NextRequest, NextResponse } from "next/server";
import { buildLineEditorPayload } from "@/lib/lineEditorAnalysis";
import { readLineDuplicateByLine, readNewBboxes } from "@/lib/repo";
import { buildCanonicalLineLayout, displayIndexForLine } from "@/lib/canonicalLines";
import { readV2Geometry } from "@/lib/pipelineReaders";

export const dynamic = "force-dynamic";

function parseParams(pageRaw: string, lineRaw: string) {
  const page = pageRaw.padStart(3, "0");
  const pageInt = parseInt(page, 10);
  const lineIndex = parseInt(lineRaw, 10);
  if (!Number.isFinite(pageInt) || !Number.isFinite(lineIndex)) return null;
  return { page, pageInt, lineIndex };
}

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ page: string; line: string }> },
) {
  const { page: pageRaw, line: lineRaw } = await ctx.params;
  const parsed = parseParams(pageRaw, lineRaw);
  if (!parsed) return NextResponse.json({ error: "invalid page or line" }, { status: 400 });

  try {
    const duplicate = readLineDuplicateByLine(parsed.pageInt, parsed.lineIndex);
    const geometryLineIndex = duplicate?.source_line_index ?? parsed.lineIndex;
    const options = duplicate
      ? {
          targetLineIndex: duplicate.line_index,
          displayIndex:
            displayIndexForLine(
              buildCanonicalLineLayout(await readV2Geometry(parsed.page)),
              duplicate.source_line_index,
            ) + duplicate.ordinal / 100,
        }
      : undefined;
    const payload = await buildLineEditorPayload(
      parsed.page,
      geometryLineIndex,
      readNewBboxes(parsed.pageInt),
      options,
    );
    if (!payload) return NextResponse.json({ error: "line not found" }, { status: 404 });
    return NextResponse.json(payload);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ error: "line editor payload failed", detail }, { status: 500 });
  }
}