import { z } from "zod";

/** Pipeline token geometry. */
export const GeometrySchema = z.object({
  warped_bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  width: z.number(),
  height: z.number(),
  area: z.number(),
  aspect: z.number(),
  center_x: z.number(),
  center_y: z.number(),
  baseline_touch: z.boolean().optional(),
  baseline_delta: z.number().optional(),
  previous_gap: z.number().nullable().optional(),
  next_gap: z.number().nullable().optional(),
});
export type Geometry = z.infer<typeof GeometrySchema>;

export const OverrideSchema = z
  .object({
    label: z.string().nullable().optional(),
    confidence: z.string().optional(),
    evidence: z.string().optional(),
    source: z.string().optional(),
  })
  .passthrough();

/** A single token / blob as it appears in line_sequences.jsonl. */
export const TokenSchema = z.object({
  page: z.string(),
  line_index: z.number(),
  v1_line_index: z.number().optional(),
  blob_id: z.number(),
  split_metadata: z.unknown().nullable().optional(),
  split_expected_base: z.string().nullable().optional(),
  split_expected_text: z.string().nullable().optional(),
  cluster: z.string(),
  label: z.string().nullable().optional(),
  manual_override: OverrideSchema.nullable().optional(),
  manual_warning: OverrideSchema.nullable().optional(),
  subcluster_override: OverrideSchema.nullable().optional(),
  geometric_override: OverrideSchema.nullable().optional(),
  editorial_override: OverrideSchema.nullable().optional(),
  review: z.boolean().optional(),
  candidates: z.array(z.string()).default([]),
  edge_fragment: z.boolean().optional(),
  overline_mark_id: z.number().nullable().optional(),
  geometry: GeometrySchema,
});
export type Token = z.infer<typeof TokenSchema>;

export const LineRecordSchema = z.object({
  page: z.string(),
  line_index: z.number(),
  tokens: z.array(TokenSchema),
});
export type LineRecord = z.infer<typeof LineRecordSchema>;

/** Body bbox JSON (pages/keph_pNNN_body_bbox.json). */
export const BodyBboxSchema = z.object({
  page_size: z.tuple([z.number(), z.number()]),
  bbox: z.object({
    x0: z.number(),
    y0: z.number(),
    x1: z.number(),
    y1: z.number(),
  }),
});
export type BodyBbox = z.infer<typeof BodyBboxSchema>;

export const LineGeometrySchema = z.object({
  line_index: z.number(),
  synthetic: z.boolean().optional(),
  warped_size: z.tuple([z.number(), z.number()]),
  baseline_y_warped: z.number().optional(),
});
export type LineGeometry = z.infer<typeof LineGeometrySchema>;

export const LinesBaseSplitSchema = z.object({
  page: z.string(),
  image_size: z.tuple([z.number(), z.number()]),
  warp_height: z.number(),
  baseline_y_warped: z.number(),
  lines: z.array(
    LineGeometrySchema.extend({
      blobs: z
        .array(
          z.object({
            id: z.number(),
            kind: z.string().optional(),
            warped_bbox: z.tuple([
              z.number(),
              z.number(),
              z.number(),
              z.number(),
            ]),
            img_quad: z
              .array(z.tuple([z.number(), z.number()]))
              .length(4)
              .optional(),
          }),
        )
        .default([]),
    }),
  ),
});
export type LinesBaseSplit = z.infer<typeof LinesBaseSplitSchema>;

/** Editing API payloads. */
export const EditBlobSchema = z.object({
  line_index: z.number(),
  blob_id: z.union([z.number(), z.string()]),
  label: z.string().nullable().optional(),
  diacritics: z.array(z.string()).nullable().optional(),
  lacuna_bracket: z.string().nullable().optional(),
  deleted: z.boolean().optional(),
  overline_mark_id: z.number().nullable().optional(),
  source: z.enum(["manual", "candidate", "cluster"]).default("manual"),
});
export type EditBlobInput = z.infer<typeof EditBlobSchema>;

export const NewBboxInputSchema = z.object({
  line_index: z.number(),
  x0: z.number(),
  y0: z.number(),
  x1: z.number(),
  y1: z.number(),
  coord_space: z.enum(["warped", "image"]).default("warped"),
  label: z.string().nullable().optional(),
  diacritics: z.array(z.string()).nullable().optional(),
  lacuna_bracket: z.string().nullable().optional(),
});
export type NewBboxInput = z.infer<typeof NewBboxInputSchema>;

export const TaskInputSchema = z.object({
  page: z.number(),
  line_index: z.number(),
  kind: z.enum(["revisit", "needs_specialist", "ambiguous"]),
  note: z.string().nullable().optional(),
});
export type TaskInput = z.infer<typeof TaskInputSchema>;

/* ---------------------------------------------------------------------------
 * Transposed v1→v2 baseline (output of scripts/projects/manual_reviewer_ingest/
 * transpose_v1_to_v2.py). v2 text_body is the canvas; tokens carry the v1
 * cluster/label/candidate state with geometry remapped into v2 coords.
 * ------------------------------------------------------------------------ */

export const BaselineTokenSchema = z.object({
  blob_id: z.number(),
  v1_line_index: z.number().optional(),
  cluster: z.string(),
  label: z.string().nullable().optional(),
  overline_mark_id: z.number().nullable().optional(),
  review_sheet_source: z.string().nullable().optional(),
  review_sheet_raw_label: z.string().nullable().optional(),
  v1_provenance: z.unknown().nullable().optional(),
  manual_override: OverrideSchema.nullable().optional(),
  manual_warning: OverrideSchema.nullable().optional(),
  geometric_override: OverrideSchema.nullable().optional(),
  editorial_override: OverrideSchema.nullable().optional(),
  subcluster_override: OverrideSchema.nullable().optional(),
  candidates: z.array(z.string()).default([]),
  review: z.boolean().optional(),
  geometry: z.object({
    img_quad: z.array(z.tuple([z.number(), z.number()])).length(4),
    aabb: z.tuple([z.number(), z.number(), z.number(), z.number()]),
    warped_bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  }),
}).passthrough();
export type BaselineToken = z.infer<typeof BaselineTokenSchema>;

export const BaselineLineSchema = z.object({
  line_index: z.number(),
  v1_line_index: z.number().optional(),
  baseline_y: z.number(),
  x_span: z.array(z.number()).length(2),
  tokens: z.array(BaselineTokenSchema),
});
export type BaselineLine = z.infer<typeof BaselineLineSchema>;

export const BaselineSchema = z.object({
  page: z.string(),
  status: z.string(),
  image: z.string(),
  image_size: z.tuple([z.number(), z.number()]),
  v1_image_size: z.tuple([z.number(), z.number()]).optional(),
  rows_v1: z.number().optional(),
  rows_v2: z.number().optional(),
  rows_aligned: z.number().optional(),
  tokens_excluded: z.number().optional(),
  lines: z.array(BaselineLineSchema),
});
export type Baseline = z.infer<typeof BaselineSchema>;
