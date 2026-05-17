"use client";

import { useEffect, useState } from "react";
import { Dialog, DialogContent } from "@mui/material";
import { CopticPicker } from "./CopticPicker";

interface Props {
  open: boolean;
  initialLabel: string | null;
  clusterId: number;
  memberCount: number;
  busy?: boolean;
  onClose: () => void;
  onSubmit: (label: string) => void;
}

/**
 * Modal wrapping {@link CopticPicker} for editing a cluster-wide label override.
 */
export function ClusterLabelDialog({
  open,
  initialLabel,
  clusterId,
  memberCount,
  busy,
  onClose,
  onSubmit,
}: Props) {
  const [value, setValue] = useState<string | null>(initialLabel);

  useEffect(() => {
    if (open) setValue(initialLabel);
  }, [open, initialLabel]);

  const handleSubmit = () => {
    if (!value) return;
    onSubmit(value);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm">
      <DialogContent sx={{ p: 0 }}>
        <CopticPicker
          title={`Cluster ${String(clusterId).padStart(3, "0")} label`}
          subtitle={`Applies to all ${memberCount} active member${memberCount === 1 ? "" : "s"} without a manual edit.`}
          value={value}
          onChange={setValue}
          onSubmit={handleSubmit}
          onCancel={onClose}
          disabled={busy || !value}
          submitLabel="Apply label"
        />
      </DialogContent>
    </Dialog>
  );
}
