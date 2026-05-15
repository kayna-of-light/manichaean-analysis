import { NextRequest, NextResponse } from "next/server";
import { createTask, readOpenTasks, resolveTask } from "@/lib/repo";
import { TaskInputSchema } from "@/lib/zodSchemas";
import { z } from "zod";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const pageParam = searchParams.get("page");
  const page = pageParam ? parseInt(pageParam, 10) : undefined;
  return NextResponse.json({ tasks: readOpenTasks(page) });
}

export async function POST(req: NextRequest) {
  const json = await req.json();
  if (json.action === "resolve") {
    const id = z.number().parse(json.id);
    resolveTask(id);
    return NextResponse.json({ ok: true });
  }
  const input = TaskInputSchema.parse(json);
  const id = createTask(input.page, input.line_index, input.kind, input.note ?? null);
  return NextResponse.json({ ok: true, id });
}
