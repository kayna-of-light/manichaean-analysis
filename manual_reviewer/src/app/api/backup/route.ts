import { NextResponse } from "next/server";
import { backupNow } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function POST() {
  try {
    const target = await backupNow();
    return NextResponse.json({ ok: true, target });
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: (err as Error).message },
      { status: 500 },
    );
  }
}
