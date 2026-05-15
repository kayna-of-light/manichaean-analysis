"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export interface ReviewToken {
  page: string;
  line_index: number;
  blob_id: number;
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
  manual_override?: { label?: string | null } | null;
  geometric_override?: { label?: string | null } | null;
  manual_warning?: unknown;
  split_metadata?: unknown;
}

export interface ReviewLine {
  line_index: number;
  tokens: ReviewToken[];
  warped_size: [number, number] | null;
  line_quad: number[][] | null;
  status: "pending" | "in_progress" | "done" | "flagged";
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

export interface BlobEditPayload {
  line_index: number;
  blob_id: number | string;
  label?: string | null;
  diacritics?: string[] | null;
  deleted?: boolean;
  overline_mark_id?: number | null;
  source?: "manual" | "candidate" | "cluster";
}

export function useEditMutation(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
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
    }) => {
      const res = await fetch(`/api/edits/${pageId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`edit failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["page", pageId] });
      qc.invalidateQueries({ queryKey: ["pages"] });
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
