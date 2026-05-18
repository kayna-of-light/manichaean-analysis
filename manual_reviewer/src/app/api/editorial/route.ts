import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { buildEditorialOverview } from "@/lib/editorial";
import {
  createEditorialClusterArray,
  createEditorialSentence,
  deleteEditorialClusterArray,
  deleteEditorialSentence,
  updateEditorialClusterArray,
  updateEditorialSentence,
} from "@/lib/repo";

export const dynamic = "force-dynamic";

const ClusterArraySchema = z.array(z.number().int()).max(200);

const ActionSchema = z.discriminatedUnion("action", [
  z.object({
    action: z.literal("create_sentence"),
    text: z.string().trim().min(1),
    active: z.boolean().optional(),
    note: z.string().nullable().optional(),
  }),
  z.object({
    action: z.literal("update_sentence"),
    id: z.number().int().positive(),
    text: z.string().trim().min(1).optional(),
    active: z.boolean().optional(),
    note: z.string().nullable().optional(),
  }),
  z.object({
    action: z.literal("delete_sentence"),
    id: z.number().int().positive(),
  }),
  z.object({
    action: z.literal("create_array"),
    sentence_id: z.number().int().positive(),
    name: z.string().nullable().optional(),
    clusters: ClusterArraySchema,
    active: z.boolean().optional(),
  }),
  z.object({
    action: z.literal("update_array"),
    id: z.number().int().positive(),
    name: z.string().nullable().optional(),
    clusters: ClusterArraySchema.optional(),
    active: z.boolean().optional(),
  }),
  z.object({
    action: z.literal("delete_array"),
    id: z.number().int().positive(),
  }),
]);

export async function GET() {
  const sentences = await buildEditorialOverview();
  return NextResponse.json({ sentences });
}

export async function POST(req: NextRequest) {
  let body: z.infer<typeof ActionSchema>;
  try {
    body = ActionSchema.parse(await req.json());
  } catch (err) {
    return NextResponse.json(
      { error: "bad request", detail: (err as Error).message },
      { status: 400 },
    );
  }

  try {
    switch (body.action) {
      case "create_sentence":
        createEditorialSentence(body.text, body.active ?? true, body.note ?? null);
        break;
      case "update_sentence":
        updateEditorialSentence(body.id, {
          text: body.text,
          active: body.active,
          note: body.note,
        });
        break;
      case "delete_sentence":
        deleteEditorialSentence(body.id);
        break;
      case "create_array":
        createEditorialClusterArray(
          body.sentence_id,
          body.clusters,
          body.name ?? null,
          body.active ?? true,
        );
        break;
      case "update_array":
        updateEditorialClusterArray(body.id, {
          clusters: body.clusters,
          name: body.name,
          active: body.active,
        });
        break;
      case "delete_array":
        deleteEditorialClusterArray(body.id);
        break;
      default:
        return NextResponse.json({ error: "unsupported action" }, { status: 400 });
    }
  } catch (err) {
    return NextResponse.json(
      { error: "mutation failed", detail: (err as Error).message },
      { status: 400 },
    );
  }

  const sentences = await buildEditorialOverview();
  return NextResponse.json({ ok: true, sentences });
}