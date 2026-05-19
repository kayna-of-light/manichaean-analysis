---
name: manual-reviewer-feature
description: >-
  Add a complete feature to the Kephalaia Manual Reviewer (manual_reviewer/).
  Covers the full vertical slice: SQLite schema migration, repo functions, Zod
  schemas, API route handler, React Query hook, Zustand store (if needed), and
  UI component. Use when building a new capability end-to-end. Keywords: feature,
  vertical slice, new, add, scaffold, CRUD, migration, schema, store, hook,
  end-to-end, full stack, manual reviewer.
---

# Manual Reviewer — Feature (Vertical Slice)

This skill covers adding a complete feature to the Kephalaia Manual Reviewer
(`manual_reviewer/`) — from database schema through API to UI.

---

## Architecture Layers

```
┌───────────────────────────────────────────────────────────┐
│  UI Component (src/components/{domain}/)                  │
│  └─ uses React Query hook for server state               │
│  └─ uses Zustand store for client-only UI state          │
├───────────────────────────────────────────────────────────┤
│  React Query Hook (src/components/reviewer/hooks.ts       │
│    or src/components/{domain}/hooks.ts)                   │
│  └─ fetch() calls to API routes                          │
├───────────────────────────────────────────────────────────┤
│  API Route (src/app/api/{resource}/route.ts)             │
│  └─ Zod validation → repo function → JSON response       │
├───────────────────────────────────────────────────────────┤
│  Repo Layer (src/lib/repo.ts)                            │
│  └─ Prepared statements, typed rows, audit logging       │
├───────────────────────────────────────────────────────────┤
│  SQLite Schema (src/lib/db.ts migrate())                 │
│  └─ CREATE TABLE IF NOT EXISTS (idempotent migrations)   │
└───────────────────────────────────────────────────────────┘
```

---

## Step 1 — SQLite Schema Migration

Add tables to the `migrate()` function in `src/lib/db.ts`. Migrations are
**idempotent** — they use `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.

```typescript
// Inside migrate() in src/lib/db.ts
db.exec(`
  CREATE TABLE IF NOT EXISTS my_things (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    page        INTEGER NOT NULL,
    line_index  INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    value       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE INDEX IF NOT EXISTS idx_my_things_page ON my_things(page);
`);
```

After adding new tables, bump `SCHEMA_VERSION` (informational; not enforced).

### Schema Rules

- Primary keys: `INTEGER PRIMARY KEY AUTOINCREMENT` for auto-ids, or composite PKs
- Timestamps: `TEXT NOT NULL DEFAULT (datetime('now'))` (ISO8601 UTC strings)
- Booleans: `INTEGER NOT NULL DEFAULT 0` (0/1)
- JSON arrays: store as `TEXT` (JSON-serialized), parse in repo layer
- Foreign keys: defined in schema, enforced by `PRAGMA foreign_keys = ON`
- Always add an index on columns used in WHERE clauses (especially `page`)

---

## Step 2 — Repo Functions

Add read/write functions to `src/lib/repo.ts`. The repo layer is the **only** place
that touches SQLite directly.

### Read Function

```typescript
export function readMyThings(page: number): MyThingRow[] {
  const db = getDb();
  return db
    .prepare("SELECT * FROM my_things WHERE page = ? ORDER BY line_index")
    .all(page) as MyThingRow[];
}
```

### Write Function

```typescript
export function createMyThing(
  page: number,
  lineIndex: number,
  kind: string,
  value: string | null,
): number {
  const db = getDb();
  const result = db
    .prepare(
      `INSERT INTO my_things (page, line_index, kind, value)
       VALUES (?, ?, ?, ?)`,
    )
    .run(page, lineIndex, kind, value);
  return Number(result.lastInsertRowid);
}
```

### Transaction Pattern (multiple writes)

```typescript
export function batchUpdateThings(updates: { id: number; value: string }[]) {
  const db = getDb();
  const stmt = db.prepare("UPDATE my_things SET value = ?, updated_at = datetime('now') WHERE id = ?");
  const tx = db.transaction((items: typeof updates) => {
    for (const item of items) {
      stmt.run(item.value, item.id);
    }
  });
  tx(updates);
}
```

### Row Types

Define row interfaces at the top of `repo.ts`:

```typescript
export interface MyThingRow {
  id: number;
  page: number;
  line_index: number;
  kind: string;
  value: string | null;
  created_at: string;
  updated_at: string;
}
```

---

## Step 3 — Zod Schemas

Add validation schemas to `src/lib/zodSchemas.ts` (shared) or inline in the route
(if route-specific).

```typescript
export const MyThingInputSchema = z.object({
  page: z.number().int().positive(),
  line_index: z.number().int().min(0),
  kind: z.string().trim().min(1),
  value: z.string().nullable().optional(),
});
export type MyThingInput = z.infer<typeof MyThingInputSchema>;
```

---

## Step 4 — API Route

Create `src/app/api/my-things/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { readMyThings, createMyThing } from "@/lib/repo";
import { MyThingInputSchema } from "@/lib/zodSchemas";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const page = parseInt(new URL(req.url).searchParams.get("page") ?? "", 10);
  if (!Number.isFinite(page)) {
    return NextResponse.json({ error: "page required" }, { status: 400 });
  }
  return NextResponse.json({ items: readMyThings(page) });
}

export async function POST(req: NextRequest) {
  let body: z.infer<typeof MyThingInputSchema>;
  try {
    body = MyThingInputSchema.parse(await req.json());
  } catch (err) {
    return NextResponse.json(
      { error: "bad request", detail: (err as Error).message },
      { status: 400 },
    );
  }
  const id = createMyThing(body.page, body.line_index, body.kind, body.value ?? null);
  return NextResponse.json({ ok: true, id });
}
```

---

## Step 5 — React Query Hook

Add hooks for the new feature. Location depends on scope:
- Page/review features: `src/components/reviewer/hooks.ts`
- Domain-specific features: `src/components/{domain}/hooks.ts`

```typescript
export function useMyThings(page: number) {
  return useQuery<{ items: MyThingRow[] }>({
    queryKey: ["myThings", page],
    queryFn: async () => {
      const res = await fetch(`/api/my-things?page=${page}`);
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    enabled: page > 0,
  });
}

export function useCreateMyThing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: MyThingInput) => {
      const res = await fetch("/api/my-things", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["myThings", vars.page] });
    },
  });
}
```

---

## Step 6 — Zustand Store (Client UI State Only)

Only needed when the feature has **ephemeral client state** (selections, open/close
states, UI mode toggles). Do NOT use Zustand for server data — that's React Query.

```typescript
// src/components/{domain}/store.ts
"use client";
import { create } from "zustand";

interface MyFeatureState {
  selectedId: number | null;
  dialogOpen: boolean;
  setSelectedId: (id: number | null) => void;
  openDialog: () => void;
  closeDialog: () => void;
}

export const useMyFeatureStore = create<MyFeatureState>((set) => ({
  selectedId: null,
  dialogOpen: false,
  setSelectedId: (id) => set({ selectedId: id }),
  openDialog: () => set({ dialogOpen: true }),
  closeDialog: () => set({ dialogOpen: false, selectedId: null }),
}));
```

### When to use Zustand vs. React Query

| Use Case | Tool |
|----------|------|
| Data from the server (persisted) | React Query |
| Which item is selected in the UI | Zustand |
| Dialog open/close state | Zustand (or local `useState`) |
| Form input values | Local `useState` |
| Data that other components need to read | Zustand |

---

## Step 7 — UI Component

Create the component in `src/components/{domain}/`:

```tsx
"use client";
import { Box, Button, List, ListItem, Typography } from "@mui/material";
import { useMyThings, useCreateMyThing } from "./hooks";

interface Props {
  page: number;
}

export function MyThingsList({ page }: Props) {
  const { data, isLoading } = useMyThings(page);
  const createMutation = useCreateMyThing();

  if (isLoading) return <Typography>Loading...</Typography>;

  return (
    <Box>
      <List>
        {data?.items.map((item) => (
          <ListItem key={item.id}>
            <Typography>{item.kind}: {item.value}</Typography>
          </ListItem>
        ))}
      </List>
      <Button
        variant="outlined"
        onClick={() => createMutation.mutate({ page, line_index: 0, kind: "note" })}
        disabled={createMutation.isPending}
      >
        Add Thing
      </Button>
    </Box>
  );
}
```

---

## Checklist

When adding a feature, verify:

- [ ] Schema migration is idempotent (`CREATE TABLE IF NOT EXISTS`)
- [ ] Repo functions use prepared statements (not string interpolation)
- [ ] Zod schema validates all user input
- [ ] API route has `export const dynamic = "force-dynamic"`
- [ ] API route returns proper error responses (400/404/500)
- [ ] React Query hook has proper `queryKey` for cache invalidation
- [ ] Mutation `onSuccess` invalidates relevant queries
- [ ] UI component handles loading and error states
- [ ] Component works in both light and dark mode
- [ ] `pnpm typecheck` passes

---

## Navigation / Routing

If the feature needs its own page:

1. Create `src/app/{route}/page.tsx`
2. Add a navigation link in `AppShell.tsx` if it's a top-level section
3. Use `Link` from `next/link` for client-side navigation

Current routes:
- `/` — Pages overview
- `/review/[page]` — Single page editor
- `/cluster` — Cluster management
- `/editorial` — Editorial fingerprint management

---

## Pipeline Data Access (Read-Only)

Features may need to read from the OCR pipeline output. Use the readers in
`src/lib/pipelineReaders.ts`:

```typescript
import { listPages, readInitialBaseline } from "@/lib/pipelineReaders";
```

**Never write to pipeline directories.** All mutations go to SQLite.
Pipeline paths are configured in `src/lib/paths.ts` via environment variables.
