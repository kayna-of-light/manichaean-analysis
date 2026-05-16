import "server-only";
import Database, { type Database as DB } from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";
import { BACKUP_DIR, DATA_DIR, DB_PATH, ensureDataDirs } from "./paths";

const SCHEMA_VERSION = 4;

let _db: DB | null = null;

/**
 * Singleton SQLite connection. Opens (or creates) the reviewer.db file,
 * enables WAL mode for durability + concurrency, and runs migrations.
 *
 * Durability strategy:
 *   - WAL journal mode (crash-safe, fsync on commit boundaries)
 *   - synchronous = NORMAL (safe with WAL, faster than FULL)
 *   - Every mutation goes through BEGIN IMMEDIATE and writes an audit_log row
 *     in the same transaction. See lib/repo.ts.
 */
export function getDb(): DB {
  if (_db) return _db;
  ensureDataDirs();
  const db = new Database(DB_PATH);
  db.pragma("journal_mode = WAL");
  db.pragma("synchronous = NORMAL");
  db.pragma("foreign_keys = ON");
  db.pragma("busy_timeout = 5000");
  // Integrity check at boot — fail-loud if storage is corrupted.
  try {
    const rows = db.pragma("integrity_check") as Array<{ integrity_check: string }>;
    const status = Array.isArray(rows) && rows[0] ? rows[0].integrity_check : "unknown";
    if (status !== "ok") {
      console.warn(`[reviewer.db] integrity_check: ${status}`);
    }
  } catch (e) {
    console.warn(`[reviewer.db] integrity_check failed: ${(e as Error).message}`);
  }
  migrate(db);
  maybeAutoBackup(db);
  _db = db;
  return db;
}

function migrate(db: DB) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS meta (
      key   TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS pages (
      page           INTEGER PRIMARY KEY,
      status         TEXT NOT NULL DEFAULT 'pending',
      last_edited_at TEXT
    );

    CREATE TABLE IF NOT EXISTS lines (
      page        INTEGER NOT NULL,
      line_index  INTEGER NOT NULL,
      status      TEXT NOT NULL DEFAULT 'pending',
      note        TEXT,
      updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
      PRIMARY KEY (page, line_index)
    );

    CREATE TABLE IF NOT EXISTS blob_edits (
      page            INTEGER NOT NULL,
      line_index      INTEGER NOT NULL,
      blob_id         TEXT NOT NULL,
      label           TEXT,
      diacritics      TEXT,
      lacuna_bracket  TEXT,
      deleted         INTEGER NOT NULL DEFAULT 0,
      source          TEXT NOT NULL DEFAULT 'manual',
      updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
      PRIMARY KEY (page, line_index, blob_id)
    );
    CREATE INDEX IF NOT EXISTS idx_blob_edits_page ON blob_edits(page);

    CREATE TABLE IF NOT EXISTS new_bboxes (
      id              TEXT PRIMARY KEY,
      page            INTEGER NOT NULL,
      line_index      INTEGER NOT NULL,
      x0              REAL NOT NULL,
      y0              REAL NOT NULL,
      x1              REAL NOT NULL,
      y1              REAL NOT NULL,
      coord_space     TEXT NOT NULL DEFAULT 'warped',
      label           TEXT,
      diacritics      TEXT,
      lacuna_bracket  TEXT,
      overline_mark_id INTEGER,
      created_at      TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_new_bboxes_page ON new_bboxes(page, line_index);

    CREATE TABLE IF NOT EXISTS cluster_overrides (
      cluster_id   INTEGER PRIMARY KEY,
      label        TEXT,
      diacritics   TEXT,
      note         TEXT,
      applied_at   TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS unset_blobs (
      page                  INTEGER NOT NULL,
      line_index            INTEGER NOT NULL,
      blob_id               TEXT NOT NULL,
      removed_from_cluster  INTEGER,
      moved_at              TEXT NOT NULL DEFAULT (datetime('now')),
      PRIMARY KEY (page, line_index, blob_id)
    );

    CREATE TABLE IF NOT EXISTS cluster_reassignments (
      page          INTEGER NOT NULL,
      line_index    INTEGER NOT NULL,
      blob_id       TEXT NOT NULL,
      from_cluster  INTEGER,
      to_cluster    INTEGER NOT NULL,
      note          TEXT,
      moved_at      TEXT NOT NULL DEFAULT (datetime('now')),
      PRIMARY KEY (page, line_index, blob_id)
    );
    CREATE INDEX IF NOT EXISTS idx_cluster_reassign_to
      ON cluster_reassignments(to_cluster);
    CREATE INDEX IF NOT EXISTS idx_cluster_reassign_from
      ON cluster_reassignments(from_cluster);

    CREATE TABLE IF NOT EXISTS tasks (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      page         INTEGER NOT NULL,
      line_index   INTEGER NOT NULL,
      kind         TEXT NOT NULL,
      note         TEXT,
      resolved     INTEGER NOT NULL DEFAULT 0,
      created_at   TEXT NOT NULL DEFAULT (datetime('now')),
      resolved_at  TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_tasks_open ON tasks(resolved, page);

    CREATE TABLE IF NOT EXISTS audit_log (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      at         TEXT NOT NULL DEFAULT (datetime('now')),
      action     TEXT NOT NULL,
      page       INTEGER,
      line_index INTEGER,
      target_id  TEXT,
      before     TEXT,
      after      TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at DESC);
  `);

  const row = db
    .prepare("SELECT value FROM meta WHERE key = 'schema_version'")
    .get() as { value: string } | undefined;
  const currentVersion = row ? parseInt(row.value, 10) : 0;

  if (!row) {
    db.prepare(
      "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
    ).run(String(SCHEMA_VERSION));
  }

  // --- Migrations ---
  if (currentVersion < 2) {
    // Add overline_mark_id column to blob_edits
    const cols = db.pragma("table_info(blob_edits)") as Array<{ name: string }>;
    if (!cols.some((c) => c.name === "overline_mark_id")) {
      db.exec("ALTER TABLE blob_edits ADD COLUMN overline_mark_id INTEGER");
    }
    db.prepare(
      "UPDATE meta SET value = ? WHERE key = 'schema_version'",
    ).run("2");
  }

  if (currentVersion < 3) {
    const cols = db.pragma("table_info(new_bboxes)") as Array<{ name: string }>;
    if (!cols.some((c) => c.name === "overline_mark_id")) {
      db.exec("ALTER TABLE new_bboxes ADD COLUMN overline_mark_id INTEGER");
    }
    db.prepare(
      "UPDATE meta SET value = ? WHERE key = 'schema_version'",
    ).run("3");
  }

  if (currentVersion < 4) {
    // cluster_reassignments is created above via CREATE IF NOT EXISTS; just bump.
    db.prepare(
      "UPDATE meta SET value = ? WHERE key = 'schema_version'",
    ).run(String(SCHEMA_VERSION));
  }
}

function maybeAutoBackup(db: DB) {
  try {
    fs.mkdirSync(BACKUP_DIR, { recursive: true });
    const entries = fs
      .readdirSync(BACKUP_DIR)
      .filter((f) => f.endsWith(".db"))
      .map((f) => ({
        name: f,
        mtime: fs.statSync(path.join(BACKUP_DIR, f)).mtimeMs,
      }))
      .sort((a, b) => b.mtime - a.mtime);
    const newest = entries[0]?.mtime ?? 0;
    const oneDay = 24 * 60 * 60 * 1000;
    if (Date.now() - newest > oneDay) {
      const stamp = new Date()
        .toISOString()
        .replace(/[:.]/g, "-")
        .slice(0, 19);
      const target = path.join(BACKUP_DIR, `reviewer-${stamp}.db`);
      // Use SQLite Online Backup API (consistent even with open writers)
      (db as unknown as { backup: (p: string) => Promise<void> })
        .backup(target)
        .catch(() => {
          // best-effort; never block startup
        });
    }
  } catch {
    // best-effort
  }
}

void DATA_DIR; // ensure import keeps tree-shake happy

/** Force an immediate backup; returns the target path. */
export async function backupNow(): Promise<string> {
  const db = getDb();
  fs.mkdirSync(BACKUP_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const target = path.join(BACKUP_DIR, `reviewer-${stamp}.db`);
  await (db as unknown as { backup: (p: string) => Promise<void> }).backup(
    target,
  );
  return target;
}
