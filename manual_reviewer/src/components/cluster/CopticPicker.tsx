"use client";

import { Box, Button, Divider, IconButton, Stack, Typography } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { ChooserPreview } from "@/components/reviewer/ChooserPreview";
import { CopticKeyboard } from "@/components/shared/CopticKeyboard";

interface Preview {
  imageUrl: string;
  imageSize: [number, number];
  aabb: [number, number, number, number];
}

interface Props {
  /** Title displayed at the top. */
  title?: string;
  /** Sub-line under the title. */
  subtitle?: string;
  /** Current label value (no diacritics). */
  value: string | null;
  onChange: (next: string | null) => void;
  onSubmit?: () => void;
  onCancel?: () => void;
  /** Hide diacritics + brackets. Defaults to true for cluster mode. */
  hideDiacritics?: boolean;
  /** Hide the "skip" affordance. Skip is enabled by default for new-cluster. */
  allowSkip?: boolean;
  onSkip?: () => void;
  preview?: Preview | null;
  /** Disable submit (e.g. while a mutation is in flight). */
  disabled?: boolean;
  submitLabel?: string;
}

/**
 * A standalone Coptic label picker mirroring the visual layout of the
 * reviewer's `CharChooser`, but with diacritics suppressed and no overline
 * group. Used for cluster label editing and the create-new-cluster flow.
 */
export function CopticPicker({
  title,
  subtitle,
  value,
  onChange,
  onSubmit,
  onCancel,
  hideDiacritics = true,
  allowSkip = false,
  onSkip,
  preview,
  disabled = false,
  submitLabel = "Save",
}: Props) {
  return (
    <Box sx={{ p: 2, minWidth: 420, maxWidth: 560 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {title && (
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }} noWrap>
              {title}
            </Typography>
          )}
          {subtitle && (
            <Typography variant="caption" color="text.secondary" noWrap>
              {subtitle}
            </Typography>
          )}
        </Box>
        {preview && (
          <ChooserPreview
            imageUrl={preview.imageUrl}
            imageSize={preview.imageSize}
            aabb={preview.aabb}
          />
        )}
        {onCancel && (
          <IconButton size="small" onClick={onCancel} aria-label="close">
            <CloseIcon fontSize="small" />
          </IconButton>
        )}
      </Stack>

      <CopticKeyboard
        mode="single"
        value={value}
        onChange={onChange}
        hideDiacritics={hideDiacritics}
      />

      <Divider sx={{ my: 1 }} />

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        {allowSkip && onSkip && (
          <Button
            size="small"
            variant="text"
            onClick={onSkip}
            disabled={disabled}
          >
            Skip (no label)
          </Button>
        )}
        {onCancel && (
          <Button size="small" variant="text" onClick={onCancel}>
            Cancel
          </Button>
        )}
        {onSubmit && (
          <Button
            size="small"
            variant="contained"
            onClick={onSubmit}
            disabled={disabled}
          >
            {submitLabel}
          </Button>
        )}
      </Stack>
    </Box>
  );
}
