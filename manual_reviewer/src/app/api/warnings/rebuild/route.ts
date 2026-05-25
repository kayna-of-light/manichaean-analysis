import { NextResponse } from "next/server";
import { execSync } from "child_process";
import path from "path";
import { invalidateModel } from "@/lib/bigramScorer";

export const dynamic = "force-dynamic";

/**
 * POST /api/warnings/rebuild
 *
 * Rebuilds the bigram model from all reviewed pages.
 * Call this after completing a batch of reviews to improve scoring accuracy.
 */
export async function POST() {
  try {
    const scriptPath = path.join(process.cwd(), "scripts", "build_bigram_model.cjs");
    execSync(`node "${scriptPath}"`, {
      cwd: process.cwd(),
      timeout: 30000,
      encoding: "utf8",
    });

    // Invalidate in-memory cache so next request uses the fresh model
    invalidateModel();

    return NextResponse.json({ ok: true, message: "Bigram model rebuilt" });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
