"use client";

import { useEffect, useState } from "react";
import { Dialog, DialogContent } from "@mui/material";
import { CopticPicker } from "./CopticPicker";

interface Props {
  open: boolean;
  /** How many blobs will move into the new cluster. */
  memberCount: number;
  busy?: boolean;
  onClose: () => void;
  /** label may be null = create cluster without a base label override. */
  onSubmit: (label: string | null) => void;
}

/**
 * Modal wrapping {@link CopticPicker} for creating a new cluster from the
 * current cluster's selection. The label is optional: skipping yields a
 * new cluster with no override (label still resolves from individual blob
 * edits if any).
 */
export function NewClusterDialog({
  open,
  memberCount,
  busy,
  onClose,
  onSubmit,
}: Props) {
  const [value, setValue] = useState<string | null>(null);

  useEffect(() => {
    if (open) setValue(null);
  }, [open]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm">
      <DialogContent sx={{ p: 0 }}>
        <CopticPicker
          title="Create new cluster from selection"
          subtitle={`${memberCount} blob${memberCount === 1 ? "" : "s"} will move into the new cluster. Picking a label is optional.`}
          value={value}
          onChange={setValue}
          onSubmit={() => onSubmit(value)}
          onSkip={() => onSubmit(null)}
          allowSkip
          onCancel={onClose}
          disabled={busy}
          submitLabel={value ? "Create with label" : "Create"}
        />
      </DialogContent>
    </Dialog>
  );
}
