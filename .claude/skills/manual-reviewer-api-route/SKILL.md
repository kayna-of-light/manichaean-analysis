---
name: manual-reviewer-api-route
description: >-
  Add or modify Next.js API route handlers in the Kephalaia Manual Reviewer
  (manual_reviewer/). Covers the route handler pattern, Zod request validation,
  SQLite repo access, dynamic params, and error handling. Use when adding new
  endpoints, fixing API bugs, or extending existing routes. Keywords: API, route,
  endpoint, handler, fetch, POST, GET, Zod, validation, SQLite, repo, server,
  Next.js route handler, manual reviewer.
---

# Manual Reviewer — API Route

This skill covers creating and modifying Next.js App Router API route handlers
for the Kephalaia Manual Reviewer (`manual_reviewer/`).

---

## Architecture

```
Client (React Query hooks)
  ↓ fetch()
Next.js Route Handler (src/app/api/*)
  ↓ validated body/params
Repo Layer (src/lib/repo.ts)
  ↓ prepared statements
SQLite (data/reviewer.db via better-sqlite3)
```

All API routes are **server-only**. The SQLite database is accessed synchronously
via `better-sqlite3` — there is no ORM, no async DB driver.

---

## File Structure

Routes follow Next.js App Router file-system routing:

```
src/app/api/
├── backup/route.ts          # POST — trigger database backup
├── cluster/[id]/route.ts    # GET — cluster details
├── clusters/route.ts        # GET — cluster list; POST — override/reassign
├── editorial/route.ts       # GET — editorial overview; POST — CRUD actions
├── edits/[page]/route.ts    # POST — save blob edits, new bboxes, line status
├── export/route.ts          # POST — export DB to JSON
├── image/route.ts           # GET — serve pipeline images
├── page/[id]/route.ts       # GET — full page data for review
├── pages/route.ts           # GET — pages list with progress
└── tasks/route.ts           # GET/POST — task management
```

---

## Route Handler Pattern

### GET Route (no body)

```typescript
import { NextRequest, NextResponse } from "next/server";
import { someReader } from "@/lib/repo";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const filter = searchParams.get("filter");

  const data = someReader(filter);
  return NextResponse.json({ data });
}
```

### GET Route with Dynamic Params

```typescript
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  // ... use id
  return NextResponse.json({ result });
}
```

### POST Route with Zod Validation

```typescript
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { someWriter } from "@/lib/repo";

export const dynamic = "force-dynamic";

const BodySchema = z.object({
  name: z.string().trim().min(1),
  value: z.number().int().positive(),
  optional_field: z.string().nullable().optional(),
});

export async function POST(req: NextRequest) {
  let body: z.infer<typeof BodySchema>;
  try {
    body = BodySchema.parse(await req.json());
  } catch (err) {
    return NextResponse.json(
      { error: "bad request", detail: (err as Error).message },
      { status: 400 },
    );
  }

  try {
    someWriter(body.name, body.value);
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json(
      { error: "internal error", detail: (err as Error).message },
      { status: 500 },
    );
  }
}
```

### POST Route with Dynamic Params

```typescript
export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ page: string }> },
) {
  const { page } = await ctx.params;
  const pageInt = parseInt(page, 10);
  if (!Number.isFinite(pageInt)) {
    return NextResponse.json({ error: "invalid page" }, { status: 400 });
  }
  // ... validate body, call repo
}
```

---

## Critical Rules

### Always set `dynamic = "force-dynamic"`

Every route reads live SQLite data. Without this, Next.js may cache responses:

```typescript
export const dynamic = "force-dynamic";
```

### Always validate with Zod

- Define schemas adjacent to the route or import from `src/lib/zodSchemas.ts`
- Use `z.discriminatedUnion` for multi-action endpoints
- Parse inside try/catch and return 400 on failure
- Use `z.infer<typeof Schema>` for the typed body

### Params are async in Next.js 16

Dynamic route params are accessed via `await ctx.params`:

```typescript
// ✅ Correct (Next.js 16)
ctx: { params: Promise<{ id: string }> }
const { id } = await ctx.params;

// ❌ Wrong (Next.js 14 pattern)
ctx: { params: { id: string } }
```

### No async DB access

`better-sqlite3` is synchronous. Do NOT await database calls:

```typescript
// ✅ Correct
const rows = getDb().prepare("SELECT ...").all();

// ❌ Wrong
const rows = await getDb().prepare("SELECT ...").all();
```

### Import "server-only" in lib modules

Modules that access the filesystem or SQLite must import `"server-only"` to prevent
accidental client bundling:

```typescript
import "server-only";
```

Route handlers are inherently server-only, so they don't need this import — but
any `@/lib/*` module they call should have it.

---

## Response Conventions

| Scenario | Response |
|----------|----------|
| Success (data) | `NextResponse.json({ data })` or `NextResponse.json({ result })` |
| Success (action) | `NextResponse.json({ ok: true })` |
| Success (with details) | `NextResponse.json({ ok: true, id, target })` |
| Validation error | `NextResponse.json({ error: "bad request", detail }, { status: 400 })` |
| Not found | `NextResponse.json({ error: "not found" }, { status: 404 })` |
| Server error | `NextResponse.json({ error: "internal error", detail }, { status: 500 })` |

---

## Connecting to React Query (Client Side)

After creating a route, add the corresponding hook in `src/components/reviewer/hooks.ts`
(for page/review domain) or a feature-specific hooks file:

```typescript
// Query (GET)
export function useMyData(id: string) {
  return useQuery<MyDataType>({
    queryKey: ["myData", id],
    queryFn: async () => {
      const res = await fetch(`/api/my-route/${id}`);
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    enabled: Boolean(id),
  });
}

// Mutation (POST)
export function useMyMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: MyPayload) => {
      const res = await fetch("/api/my-route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["myData"] });
    },
  });
}
```

---

## Multi-Action Endpoints

For CRUD on a single resource, use discriminated union schemas:

```typescript
const ActionSchema = z.discriminatedUnion("action", [
  z.object({ action: z.literal("create"), name: z.string() }),
  z.object({ action: z.literal("update"), id: z.number(), name: z.string() }),
  z.object({ action: z.literal("delete"), id: z.number() }),
]);
```

Handle each case in a switch:

```typescript
switch (body.action) {
  case "create":
    createThing(body.name);
    break;
  case "update":
    updateThing(body.id, body.name);
    break;
  case "delete":
    deleteThing(body.id);
    break;
}
```

---

## Image Serving Route

For binary responses (images), use raw `Response`:

```typescript
import fs from "node:fs";
import path from "node:path";

export async function GET(req: NextRequest) {
  const filePath = resolveImagePath(req);
  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const buffer = fs.readFileSync(filePath);
  return new Response(buffer, {
    headers: {
      "Content-Type": "image/jpeg",
      "Cache-Control": "public, max-age=86400, immutable",
    },
  });
}
```

---

## Development Tips

- Test routes with `curl` or browser fetch in devtools
- Check `pnpm typecheck` after adding routes — type errors in route signatures
  are common (especially the async params pattern)
- Route files must export named functions (`GET`, `POST`, `PUT`, `DELETE`)
- The dev server auto-reloads on route file changes
