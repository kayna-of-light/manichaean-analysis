"use client";

import { useEffect, useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material";

interface Props {
  open: boolean;
  sentenceId: number;
  busy?: boolean;
  onClose: () => void;
  onSubmit: (name: string | null) => void;
}

export function CreateArrayDialog({ open, busy, onClose, onSubmit }: Props) {
  const [name, setName] = useState("");

  useEffect(() => {
    if (open) setName("");
  }, [open]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Add Cluster Array</DialogTitle>
      <DialogContent>
        <TextField
          label="Array name (optional)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          fullWidth
          autoFocus
          sx={{ mt: 1 }}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSubmit(name.trim() || null);
          }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={busy} onClick={() => onSubmit(name.trim() || null)}>
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
}
