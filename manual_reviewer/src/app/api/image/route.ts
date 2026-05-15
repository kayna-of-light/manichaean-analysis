import { NextRequest } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { IMAGE_ROOTS } from "@/lib/paths";

export const dynamic = "force-dynamic";

const MIME: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
};

/**
 * Whitelisted image proxy.
 *
 * Query parameters:
 *   ?p=<filename>             Resolves under PIPELINE.pages by default
 *   ?root=<key>&p=<file>      Resolves under the entry matching <key>:
 *                               - pages       (v1 page images)
 *                               - clusters    (v1 cluster thumbnails)
 *                               - textbody    (v2 text_body crops, leading canvas)
 *                               - pages_v2    (v2 pages_cropped)
 */
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const p = searchParams.get("p");
  const root = searchParams.get("root") ?? "pages";
  if (!p) return new Response("missing p", { status: 400 });

  const entry = IMAGE_ROOTS.find((r) => r.key === root);
  if (!entry) return new Response("invalid root", { status: 400 });
  const rootDir = entry.dir;

  const resolved = path.resolve(rootDir, p);
  if (!resolved.startsWith(path.resolve(rootDir) + path.sep)) {
    return new Response("forbidden", { status: 403 });
  }
  if (!fs.existsSync(resolved)) {
    return new Response("not found", { status: 404 });
  }
  const ext = path.extname(resolved).toLowerCase();
  const type = MIME[ext] ?? "application/octet-stream";
  const data = await fs.promises.readFile(resolved);
  return new Response(new Uint8Array(data), {
    status: 200,
    headers: {
      "Content-Type": type,
      "Cache-Control": "public, max-age=86400",
    },
  });
}
