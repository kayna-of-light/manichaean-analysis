# Kephalaia · Manual Reviewer

Next.js webapp for manual line-by-line correction of the Kephalaia OCR pipeline output.

Glass-design UI · MUI v9 + Tailwind v4 · SQLite (WAL) persistence · keyboard-first Coptic typing.

> Pipeline outputs in `../output/projects/kephalaia_ocr/` are **read-only**. All
> corrections are stored in `data/reviewer.db` and can be exported on demand.

## Setup

Requires Node ≥ 20 and `pnpm` (via Corepack):

```pwsh
corepack enable
pnpm install
pnpm dev
```

App opens at <http://localhost:3000>.

## Env vars (optional)

| Variable           | Default                                  | Purpose                                  |
|--------------------|------------------------------------------|------------------------------------------|
| `KEPH_OUTPUT_DIR`  | `../output/projects/kephalaia_ocr`       | Source pipeline outputs (read-only).     |
| `KEPH_DATA_DIR`    | `./data`                                 | SQLite db, backups, exports.             |

## Scripts

| Command         | Purpose                              |
|-----------------|--------------------------------------|
| `pnpm dev`      | Run dev server with Turbopack.       |
| `pnpm build`    | Production build.                    |
| `pnpm start`    | Run production build.                |
| `pnpm lint`     | Lint.                                |
| `pnpm typecheck`| `tsc --noEmit`.                      |

## Plan

See [PLAN.md](./PLAN.md) for the full scope, schema, and phased checklist.
