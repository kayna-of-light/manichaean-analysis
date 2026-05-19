"use client";

import { useEffect, useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
} from "@mui/material";

interface Props {
  open: boolean;
  busy?: boolean;
  onClose: () => void;
  onSubmit: (text: string, note: string | null) => void;
}

export function CreateSentenceDialog({ open, busy, onClose, onSubmit }: Props) {
  const [text, setText] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (open) {
      setText("");
      setNote("");
    }
  }, [open]);

  const canSubmit = text.trim().length > 0 && !busy;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Add Editorial Sentence</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="Sentence text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            fullWidth
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && canSubmit) onSubmit(text.trim(), note.trim() || null);
            }}
          />
          <TextField
            label="Note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!canSubmit}
          onClick={() => onSubmit(text.trim(), note.trim() || null)}
        >
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
}
