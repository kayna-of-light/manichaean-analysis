---
name: manual-reviewer-ui-component
description: >-
  Build UI components for the Kephalaia Manual Reviewer (manual_reviewer/).
  Covers MUI 9 + Tailwind 4 glass morphism theme, design tokens, dark mode,
  component composition, and accessibility. Use when creating or styling
  components, pages, dialogs, or layouts in manual_reviewer/. Keywords: UI,
  component, MUI, Material UI, Tailwind, glass, theme, dark mode, style,
  layout, dialog, page, card, Coptic, reviewer, manual reviewer.
---

# Manual Reviewer — UI Component

This skill covers building UI components for the Kephalaia Manual Reviewer app
(`manual_reviewer/`), a Next.js 16 App Router application using MUI 9 + Tailwind 4
with a glass morphism design system.

---

## Stack

| Package | Version | Purpose |
|---------|---------|---------|
| Next.js | 16 | App Router framework |
| React | 19 | UI library |
| MUI | 9 | Component library (with Emotion) |
| Tailwind CSS | 4 | Utility-first CSS (CSS-first config) |
| Zustand | 5 | Client state stores |
| TanStack React Query | 5 | Server state / data fetching |

---

## Design System: Glass Morphism

The app uses a **glass morphism** design language with frosted surfaces, backdrop blur,
and translucent layers. Tokens are defined in `src/app/globals.css` using Tailwind 4's
CSS-first `@theme` directive.

### Token Reference

| Token | Light | Dark | Purpose |
|-------|-------|------|---------|
| `--color-glass-bg` | `oklch(98% 0.01 80)` | `oklch(14% 0.02 260)` | Page background |
| `--color-glass-surface` | `oklch(100% 0 0 / 0.06)` | `oklch(100% 0 0 / 0.05)` | Elevated glass surfaces |
| `--color-glass-border` | `oklch(0% 0 0 / 0.12)` | `oklch(100% 0 0 / 0.10)` | Surface borders |
| `--color-glass-fg` | `oklch(20% 0.02 260)` | `oklch(96% 0.01 80)` | Primary text |
| `--color-glass-muted` | `oklch(45% 0.02 260)` | `oklch(70% 0.02 260)` | Secondary/muted text |
| `--color-glass-accent` | `#c8a465` | `#c8a465` | Brand accent (golden) |
| `--color-glass-accent-strong` | `#a07a36` | `#a07a36` | Accent emphasis |

### Status Colors

| Token | Value | Purpose |
|-------|-------|---------|
| `--color-status-pending` | `oklch(70% 0.02 260)` | Pending state |
| `--color-status-progress` | `oklch(75% 0.13 80)` | In-progress state |
| `--color-status-done` | `oklch(65% 0.16 145)` | Done/completed state |
| `--color-status-flagged` | `oklch(65% 0.20 25)` | Flagged/attention state |

### Fonts

| Token | Stack | Usage |
|-------|-------|-------|
| `--font-sans` | Inter, Segoe UI, system-ui | All UI text |
| `--font-coptic` | Noto Sans Coptic, Antinoou, New Athena Unicode | Coptic character display |
| `--font-mono` | SF Mono, Cascadia Mono, Menlo | Code, IDs, technical values |

---

## Dark Mode

- Strategy: **data-attribute** (`[data-theme="dark"]` on `<html>`)
- Managed by `ThemeProvider` at `src/components/theme/ThemeProvider.tsx`
- MUI theme built dynamically via `buildTheme(mode)` in `src/components/theme/theme.ts`
- Token overrides in `globals.css` under `[data-theme="dark"]` selector
- Persisted to `localStorage` key `kmr.theme`

**All components must work in both modes without conditional class names.** The tokens
handle the switch automatically.

---

## Glass Surface Pattern

The standard glass surface is a CSS utility class:

```css
.glass {
  background: var(--color-glass-surface);
  border: 1px solid var(--color-glass-border);
  backdrop-filter: blur(20px) saturate(140%);
  -webkit-backdrop-filter: blur(20px) saturate(140%);
}
```

For MUI Paper components, the theme already applies this via `MuiPaper` style overrides.
Do NOT re-apply backdrop-filter on MUI Paper — it's handled globally.

---

## Color Rules

**DO:**
- Use glass tokens via Tailwind utilities: `bg-glass-surface`, `text-glass-fg`, `border-glass-border`
- Use `var(--color-glass-*)` in MUI `sx` props when needed
- Use oklch color-mix for tints: `color-mix(in oklch, var(--color-glass-accent), transparent 50%)`
- Use MUI palette colors for interactive elements: `color="primary"`, `color="secondary"`

**DON'T:**
- Use raw hex/rgb values in component files
- Use Tailwind gray scale directly (`text-gray-500`, `bg-gray-100`)
- Override MUI Paper backdrop-filter (already set in theme)
- Use `className` for opacity when MUI `sx` has alpha support

---

## MUI Theme Integration

The theme is built in `src/components/theme/theme.ts`:

| MUI Palette | Value | Meaning |
|-------------|-------|---------|
| `primary.main` | `#c8a465` | Golden accent — buttons, active states |
| `secondary.main` | `#6f87b0` | Blue accent — secondary interactive |
| `background.default` | transparent | Allows glass bg gradient to show through |
| `background.paper` | translucent white/dark | Glass surface for Paper components |

### MUI Component Overrides (already configured)

- `MuiPaper` — backdrop-filter glass effect, no elevation shadows
- `MuiAppBar` — transparent with blur, sticky
- `MuiButton` — no elevation, rounded (10px), no uppercase
- `MuiIconButton` — uses `--color-glass-fg`, disabled uses muted

**Do not re-override** these in component `sx` props unless intentionally diverging.

---

## Component Patterns

### Client Components

All interactive components use the `"use client"` directive. Pages that fetch data
use React Query hooks from `src/components/reviewer/hooks.ts`.

```tsx
"use client";
import { Box, Typography } from "@mui/material";

export function MyComponent() {
  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h6">Title</Typography>
    </Box>
  );
}
```

### Layout Structure

The app uses a fixed layout hierarchy:

```
RootLayout (server)
  └─ AppRouterCacheProvider (Emotion SSR)
     └─ ThemeProvider (MUI + dark mode state)
        └─ QueryProvider (React Query)
           └─ AppShell (AppBar + Snackbar + content area)
              └─ Page content
```

### Page Components

Pages live in `src/app/` following Next.js App Router conventions.
Each page route is a directory with `page.tsx`:

```
src/app/
├── page.tsx                    # Home / pages overview
├── review/[page]/page.tsx      # Single page review (main editor)
├── cluster/page.tsx            # Cluster management
└── editorial/page.tsx          # Editorial fingerprint management
```

### Dialogs

Dialogs use MUI's `Dialog` component. Example pattern:

```tsx
"use client";
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from "@mui/material";

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: (data: SomeType) => void;
}

export function MyDialog({ open, onClose, onConfirm }: Props) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Title</DialogTitle>
      <DialogContent>
        {/* form content */}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => onConfirm(data)}>
          Confirm
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

### Coptic Text Display

Use the `.coptic` utility class (or `fontFamily: "var(--font-coptic)"` in `sx`)
for any Coptic character rendering:

```tsx
<Typography className="coptic" sx={{ fontSize: "1.2rem" }}>
  ⲁⲃⲅⲇⲉ
</Typography>
```

---

## File Location Convention

| Type | Location |
|------|----------|
| Shared components | `src/components/{domain}/` |
| Page components | `src/app/{route}/page.tsx` |
| Providers | `src/components/providers/` |
| Theme | `src/components/theme/` |
| Layout shell | `src/components/layout/` |
| CSS tokens | `src/app/globals.css` |

Domain directories: `reviewer/`, `cluster/`, `editorial/`, `layout/`, `providers/`, `theme/`

---

## Accessibility

- All `IconButton` components MUST have `aria-label`
- Use `Tooltip` wrapping for icon-only buttons
- Keyboard navigation: the Coptic picker supports physical keyboard input
- Color contrast: glass surfaces use sufficient contrast via token design
- Focus visible: MUI handles focus rings; don't suppress them

---

## Development Commands

```bash
cd manual_reviewer
pnpm dev --port 3002    # Start dev server
pnpm typecheck          # TypeScript validation
pnpm lint               # ESLint
pnpm build              # Production build
```
