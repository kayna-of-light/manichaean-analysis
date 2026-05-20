"use client";
import { create } from "zustand";

export interface OverlineNeighbor {
  blobId: string | number;
  label: string | null;
  overlineMarkId: number | null;
  isNewBbox?: boolean;
}

export interface ChooserPreview {
  imageUrl: string;
  imageSize: [number, number];
  /** [x0, y0, x1, y1] in image-space pixels. */
  aabb: [number, number, number, number];
}

export interface ChooserAnchor {
  page: string;
  pageInt: number;
  lineIndex: number;
  blobId: string | number;
  cluster: string | null;
  currentLabel: string | null;
  currentDiacritics: string[];
  candidates: string[];
  hasOverline: boolean;
  overlineMarkId: number | null;
  leftNeighbor: OverlineNeighbor | null;
  rightNeighbor: OverlineNeighbor | null;
  isNewBbox?: boolean;
  /** Optional crop info for the upper-right preview in the chooser. */
  preview?: ChooserPreview | null;
  // Staged overline changes (null = no change, number = set, -1 = clear)
  pendingOverline: {
    self: number | null | undefined;      // undefined = no change
    left: number | null | undefined;
    right: number | null | undefined;
  };
}

interface ReviewerState {
  selectedLine: number | null;
  selectedBlobId: string | number | null;
  chooserOpen: boolean;
  chooserAnchor: ChooserAnchor | null;
  setSelectedLine: (idx: number | null) => void;
  selectBlob: (lineIndex: number, blobId: string | number | null) => void;
  openChooser: (anchor: ChooserAnchor) => void;
  closeChooser: () => void;
  updateChooserLabel: (label: string | null, diacritics?: string[]) => void;
  toggleOverlineLeft: () => void;
  toggleOverlineRight: () => void;
  toggleOverlineSelf: () => void;
}

export const useReviewerStore = create<ReviewerState>((set) => ({
  selectedLine: null,
  selectedBlobId: null,
  chooserOpen: false,
  chooserAnchor: null,
  setSelectedLine: (idx) =>
    set((s) => (s.selectedLine === idx ? s : { selectedLine: idx })),
  selectBlob: (lineIndex, blobId) =>
    set((s) =>
      s.selectedLine === lineIndex && s.selectedBlobId === blobId
        ? s
        : { selectedLine: lineIndex, selectedBlobId: blobId },
    ),
  openChooser: (anchor) =>
    set({ chooserOpen: true, chooserAnchor: anchor }),
  closeChooser: () => set({ chooserOpen: false, chooserAnchor: null }),
  updateChooserLabel: (label, diacritics) =>
    set((s) => {
      if (!s.chooserAnchor) return s;
      return {
        chooserAnchor: {
          ...s.chooserAnchor,
          currentLabel: label,
          currentDiacritics: diacritics ?? s.chooserAnchor.currentDiacritics,
        },
      };
    }),
  toggleOverlineLeft: () =>
    set((s) => {
      if (!s.chooserAnchor) return s;
      const a = s.chooserAnchor;
      const leftNeighbor = a.leftNeighbor;
      if (!leftNeighbor) return s;
      const pending = { ...a.pendingOverline };
      // Effective current state
      const selfId = pending.self !== undefined ? pending.self : a.overlineMarkId;
      const leftId = pending.left !== undefined ? pending.left : leftNeighbor.overlineMarkId;
      const connected = selfId != null && leftId != null && selfId === leftId;

      if (connected) {
        // Disconnect: clear left, and if right isn't connected either, clear self
        pending.left = null;
        const rightId = pending.right !== undefined ? pending.right : a.rightNeighbor?.overlineMarkId;
        const rightConnected = rightId != null && selfId != null && rightId === selfId;
        if (!rightConnected) pending.self = null;
      } else {
        // Connect: give both the same mark_id
        const markId = selfId ?? leftId ?? Date.now();
        pending.self = markId;
        pending.left = markId;
      }
      return { chooserAnchor: { ...a, pendingOverline: pending } };
    }),
  toggleOverlineRight: () =>
    set((s) => {
      if (!s.chooserAnchor) return s;
      const a = s.chooserAnchor;
      const rightNeighbor = a.rightNeighbor;
      if (!rightNeighbor) return s;
      const pending = { ...a.pendingOverline };
      const selfId = pending.self !== undefined ? pending.self : a.overlineMarkId;
      const rightId = pending.right !== undefined ? pending.right : rightNeighbor.overlineMarkId;
      const connected = selfId != null && rightId != null && selfId === rightId;

      if (connected) {
        pending.right = null;
        const leftId = pending.left !== undefined ? pending.left : a.leftNeighbor?.overlineMarkId;
        const leftConnected = leftId != null && selfId != null && leftId === selfId;
        if (!leftConnected) pending.self = null;
      } else {
        const markId = selfId ?? rightId ?? Date.now();
        pending.self = markId;
        pending.right = markId;
      }
      return { chooserAnchor: { ...a, pendingOverline: pending } };
    }),
  toggleOverlineSelf: () =>
    set((s) => {
      if (!s.chooserAnchor) return s;
      const a = s.chooserAnchor;
      const pending = { ...a.pendingOverline };
      const selfId = pending.self !== undefined ? pending.self : a.overlineMarkId;

      if (selfId != null) {
        // Remove self from group — only clear self, neighbors keep their marks
        pending.self = null;
      } else {
        // Create a new solo overline mark
        pending.self = Date.now();
      }
      return { chooserAnchor: { ...a, pendingOverline: pending } };
    }),
}));
