"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export interface ReviewToken {
  page: string;
  line_index: number;
  v1_line_index?: number;
  blob_id: number;
  edit_id?: string;
  cluster: string;
  label: string | null;
  effective_label: string | null;
  user_modified: boolean;
  unset: boolean;
  deleted: boolean;
  review?: boolean;
  candidates: string[];
  overline_mark_id?: number | null;
  geometry: {
    warped_bbox: [number, number, number, number];
    width: number;
    height: number;
    baseline_touch?: boolean;
  };
  img_quad: number[][] | null;
  user_edit?: {
    label: string | null;
    diacritics: string | null;
  };
  editorial_overlay?: {
    label: string;
    sentence_id: number;
    array_id: number;
    sentence_text: string;
    span_position: number;
    span_count: number;
    cluster_array: number[];
  };
  manual_override?: { label?: string | null } | null;
  geometric_override?: { label?: string | null } | null;
  editorial_override?: {
    label?: string | null;
    marker_type?: string;
    marker_text?: string;
    span_position?: number;
    span_count?: number;
    confidence?: string;
  } | null;
  manual_warning?: unknown;
  split_metadata?: unknown;
}

export interface ReviewLine {
  line_index: number;
  display_index?: number;
  tokens: ReviewToken[];
  warped_size: [number, number] | null;
  line_quad: number[][] | null;
  status: "pending" | "in_progress" | "done" | "flagged" | "special";
  note: string | null;
}

export interface ReviewPage {
  page: string;
  page_int: number;
  image_size: [number, number];
  page_size: [number, number];
  bbox: { x0: number; y0: number; x1: number; y1: number };
  baseline_y_warped: number;
  warp_height: number;
  image_url: string;
  lines: ReviewLine[];
  new_bboxes: {
    id: string;
    line_index: number;
    x0: number;
    y0: number;
    x1: number;
    y1: number;
    coord_space: string;
    label: string | null;
    diacritics?: string[] | null;
    overline_mark_id?: number | null;
  }[];
}

export function usePageData(pageId: string) {
  return useQuery<ReviewPage>({
    queryKey: ["page", pageId],
    queryFn: async () => {
      const res = await fetch(`/api/page/${pageId}`);
      if (!res.ok) throw new Error(`page ${pageId} not found`);
      return res.json();
    },
    enabled: Boolean(pageId),
  });
}

// ─── Bigram warnings ──────────────────────────────────────────────────────────

export interface TokenWarningEntry {
  lineIndex: number;
  blobId: number | string;
  level: "warn" | "alert";
  reasons: string[];
}

interface WarningsResponse {
  page: number;
  warnings: TokenWarningEntry[];
  stats: { total_tokens: number; warnings_count: number; alerts_count: number };
}

export function usePageWarnings(pageId: string) {
  return useQuery<WarningsResponse>({
    queryKey: ["warnings", pageId],
    queryFn: async () => {
      const res = await fetch(`/api/warnings/${pageId}`);
      if (!res.ok) throw new Error("Failed to load warnings");
      return res.json();
    },
    enabled: Boolean(pageId),
    staleTime: 5 * 60 * 1000, // cache for 5 minutes
  });
}

export interface BlobEditPayload {
  line_index: number;
  blob_id: number | string;
  label?: string | null;
  diacritics?: string[] | null;
  deleted?: boolean;
  overline_mark_id?: number | null;
  source?: "manual" | "candidate" | "cluster";
}

export interface EditMutationPayload {
  blob_edits?: BlobEditPayload[];
  new_bboxes?: {
    line_index: number;
    x0: number;
    y0: number;
    x1: number;
    y1: number;
    coord_space?: "warped" | "image";
    label?: string | null;
  }[];
  update_new_bboxes?: {
    id: string;
    label?: string | null;
    diacritics?: string[];
    overline_mark_id?: number | null;
  }[];
  delete_new_bboxes?: string[];
  line_status?: { line_index: number; status: string; note?: string | null };
  reset_line?: { line_index: number };
}

interface EditMutationResult {
  ok: boolean;
  results?: {
    new_bboxes?: string[];
    deleted_bboxes?: string[];
  };
}

interface EditMutationContext {
  optimistic: boolean;
  previousPage?: ReviewPage;
  previousPages?: { pages: PageListItem[] };
}

function tokenEditId(token: ReviewToken): string {
  return token.edit_id ?? String(token.blob_id);
}

function applyBlobEdit(token: ReviewToken, edit: BlobEditPayload): ReviewToken {
  const deleted = edit.deleted ?? false;
  const next: ReviewToken = {
    ...token,
    deleted,
    user_modified: true,
  };

  if (edit.label !== undefined) {
    next.effective_label = deleted ? null : edit.label;
    next.unset = !deleted && edit.label === "";
    next.user_edit = {
      label: edit.label,
      diacritics:
        edit.diacritics !== undefined
          ? JSON.stringify(edit.diacritics)
          : (token.user_edit?.diacritics ?? null),
    };
  }

  if (edit.diacritics !== undefined) {
    next.user_edit = {
      label: next.user_edit?.label ?? token.user_edit?.label ?? null,
      diacritics: JSON.stringify(edit.diacritics),
    };
  }

  if (edit.overline_mark_id !== undefined) {
    next.overline_mark_id = edit.overline_mark_id;
  }

  return next;
}

function applyEditPayload(
  page: ReviewPage,
  payload: EditMutationPayload,
  result: EditMutationResult,
): ReviewPage | null {
  if (payload.reset_line) return null;

  let changed = false;
  let nextPage = page;

  if (payload.blob_edits?.length) {
    const editsByLine = new Map<number, BlobEditPayload[]>();
    for (const edit of payload.blob_edits) {
      const lineEdits = editsByLine.get(edit.line_index) ?? [];
      lineEdits.push(edit);
      editsByLine.set(edit.line_index, lineEdits);
    }

    const lines = nextPage.lines.map((line) => {
      const lineEdits = editsByLine.get(line.line_index);
      if (!lineEdits) return line;
      let lineChanged = false;
      const tokens = line.tokens.map((token) => {
        const edit = lineEdits.find((candidate) => String(candidate.blob_id) === tokenEditId(token));
        if (!edit) return token;
        lineChanged = true;
        return applyBlobEdit(token, edit);
      });
      if (!lineChanged) return line;
      changed = true;
      return { ...line, tokens };
    });
    if (changed) nextPage = { ...nextPage, lines };
  }

  if (payload.new_bboxes?.length) {
    const ids = result.results?.new_bboxes ?? [];
    if (ids.length < payload.new_bboxes.length) return null;
    nextPage = {
      ...nextPage,
      new_bboxes: [
        ...nextPage.new_bboxes,
        ...payload.new_bboxes.map((bbox, index) => ({
          id: ids[index],
          line_index: bbox.line_index,
          x0: bbox.x0,
          y0: bbox.y0,
          x1: bbox.x1,
          y1: bbox.y1,
          coord_space: bbox.coord_space ?? "warped",
          label: bbox.label ?? null,
          diacritics: null,
          overline_mark_id: null,
        })),
      ],
    };
    changed = true;
  }

  if (payload.update_new_bboxes?.length) {
    const updates = new Map(payload.update_new_bboxes.map((update) => [update.id, update]));
    nextPage = {
      ...nextPage,
      new_bboxes: nextPage.new_bboxes.map((bbox) => {
        const update = updates.get(bbox.id);
        if (!update) return bbox;
        changed = true;
        return {
          ...bbox,
          label: update.label !== undefined ? update.label : bbox.label,
          diacritics: update.diacritics !== undefined ? update.diacritics : bbox.diacritics,
          overline_mark_id:
            update.overline_mark_id !== undefined
              ? update.overline_mark_id
              : (bbox.overline_mark_id ?? null),
        };
      }),
    };
  }

  if (payload.delete_new_bboxes?.length) {
    const deletedIds = new Set(result.results?.deleted_bboxes ?? payload.delete_new_bboxes);
    const newBboxes = nextPage.new_bboxes.filter((bbox) => !deletedIds.has(bbox.id));
    if (newBboxes.length !== nextPage.new_bboxes.length) {
      nextPage = { ...nextPage, new_bboxes: newBboxes };
      changed = true;
    }
  }

  if (payload.line_status) {
    const lines = nextPage.lines.map((line) => {
      if (line.line_index !== payload.line_status?.line_index) return line;
      changed = true;
      return {
        ...line,
        status: payload.line_status.status as ReviewLine["status"],
        note: payload.line_status.note !== undefined ? payload.line_status.note : line.note,
      };
    });
    nextPage = { ...nextPage, lines };
  }

  return changed ? nextPage : null;
}

function updatePagesListCache(
  old: { pages: PageListItem[] } | undefined,
  pageId: string,
  page: ReviewPage,
): { pages: PageListItem[] } | undefined {
  if (!old) return old;
  const doneLines = page.lines.filter((line) => line.status === "done").length;
  const flaggedLines = page.lines.filter((line) => line.status === "flagged").length;
  const specialLines = page.lines.filter((line) => line.status === "special").length;
  const completedLines = doneLines + specialLines;
  return {
    pages: old.pages.map((item) => {
      if (item.page !== pageId) return item;
      return {
        ...item,
        status: completedLines === page.lines.length ? "complete" : "in_progress",
        last_edited_at: new Date().toISOString(),
        done_lines: doneLines,
        flagged_lines: flaggedLines,
        special_lines: specialLines,
        total_lines: page.lines.length,
      };
    }),
  };
}

export function useEditMutation(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: EditMutationPayload) => {
      const res = await fetch(`/api/edits/${pageId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`edit failed: ${res.status}`);
      return res.json();
    },
    onMutate: async (payload): Promise<EditMutationContext> => {
      if (payload.reset_line || payload.new_bboxes?.length) return { optimistic: false };

      await qc.cancelQueries({ queryKey: ["page", pageId] });
      const previousPage = qc.getQueryData<ReviewPage>(["page", pageId]);
      const previousPages = qc.getQueryData<{ pages: PageListItem[] }>(["pages"]);
      if (!previousPage) return { optimistic: false };

      const optimisticResult: EditMutationResult = {
        ok: true,
        results: { deleted_bboxes: payload.delete_new_bboxes ?? [] },
      };
      const nextPage = applyEditPayload(previousPage, payload, optimisticResult);
      if (!nextPage) return { optimistic: false, previousPage, previousPages };

      qc.setQueryData(["page", pageId], nextPage);
      if (payload.line_status) {
        qc.setQueryData<{ pages: PageListItem[] }>(["pages"], (old) =>
          updatePagesListCache(old, pageId, nextPage),
        );
      }
      return { optimistic: true, previousPage, previousPages };
    },
    onError: (_error, _payload, context) => {
      if (!context?.optimistic) return;
      if (context.previousPage) qc.setQueryData(["page", pageId], context.previousPage);
      if (context.previousPages) qc.setQueryData(["pages"], context.previousPages);
    },
    onSuccess: (result: EditMutationResult, payload, context) => {
      if (context?.optimistic) return;
      let nextPage: ReviewPage | null = null;
      qc.setQueryData<ReviewPage>(["page", pageId], (old) => {
        if (!old) return old;
        nextPage = applyEditPayload(old, payload, result);
        return nextPage ?? old;
      });

      if (!nextPage) {
        qc.invalidateQueries({ queryKey: ["page", pageId] });
      }

      if (payload.line_status && nextPage) {
        qc.setQueryData<{ pages: PageListItem[] }>(["pages"], (old) =>
          updatePagesListCache(old, pageId, nextPage as ReviewPage),
        );
      } else if (payload.reset_line) {
        qc.invalidateQueries({ queryKey: ["pages"] });
      }

      // Invalidate warnings so dots refresh after edits
      qc.invalidateQueries({ queryKey: ["warnings", pageId] });
    },
  });
}

export function useMoveLine(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (params: {
      page: number;
      line_index: number;
      blob_id: number | string;
      direction: "up" | "down";
      is_new_bbox: boolean;
    }) => {
      const res = await fetch("/api/move-line", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error ?? `move-line failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["page", pageId] });
      qc.invalidateQueries({ queryKey: ["warnings", pageId] });
    },
  });
}

export interface PageListItem {
  page: string;
  pageInt: number;
  status: string;
  last_edited_at: string | null;
  done_lines: number;
  flagged_lines: number;
  special_lines: number;
  total_lines: number;
}

export function usePagesList() {
  return useQuery<{ pages: PageListItem[] }>({
    queryKey: ["pages"],
    queryFn: async () => {
      const res = await fetch("/api/pages");
      if (!res.ok) throw new Error("failed to load pages");
      return res.json();
    },
  });
}
