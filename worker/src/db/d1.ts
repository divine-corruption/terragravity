/** Thin D1 helpers — job + log persistence. */
import type { JobStatus, JobType } from "../lib/types";

export function uuid(): string {
  return crypto.randomUUID();
}

export function now(): number {
  return Math.floor(Date.now() / 1000);
}

export async function createJob(
  db: D1Database,
  args: { id: string; user_id: string; type: JobType; prompt: string },
): Promise<void> {
  const t = now();
  await db
    .prepare(
      `INSERT INTO jobs (id, user_id, type, status, prompt, created_at, updated_at)
       VALUES (?, ?, ?, 'queued', ?, ?, ?)`,
    )
    .bind(args.id, args.user_id, args.type, args.prompt, t, t)
    .run();
}

export async function updateJob(
  db: D1Database,
  id: string,
  patch: Partial<{
    status: JobStatus;
    response: string;
    error: string;
    tokens_in: number;
    tokens_out: number;
    exec_ms: number;
    r2_key: string;
  }>,
): Promise<void> {
  // Skip keys whose value is undefined — including them would bind `undefined`
  // into the prepared statement, which D1 rejects with D1_TYPE_ERROR. A caller
  // passing `undefined` means "leave this column unchanged".
  const fields = Object.keys(patch).filter(
    (f) => (patch as Record<string, unknown>)[f] !== undefined,
  );
  if (fields.length === 0) return;
  const set = fields.map((f) => `${f} = ?`).join(", ");
  const values = fields.map((f) => (patch as Record<string, unknown>)[f]);
  await db
    .prepare(`UPDATE jobs SET ${set}, updated_at = ? WHERE id = ?`)
    .bind(...values, now(), id)
    .run();
}

export async function getJob(db: D1Database, id: string): Promise<Record<string, unknown> | null> {
  const row = await db.prepare(`SELECT * FROM jobs WHERE id = ?`).bind(id).first();
  return row ?? null;
}

export async function writeLog(
  db: D1Database,
  args: {
    request_uuid: string;
    user_id: string | null;
    route: string;
    status: number;
    exec_ms?: number;
    tokens?: number;
    error?: string;
  },
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO logs (id, request_uuid, user_id, route, status, exec_ms, tokens, error, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      uuid(),
      args.request_uuid,
      args.user_id,
      args.route,
      args.status,
      args.exec_ms ?? null,
      args.tokens ?? null,
      args.error ?? null,
      now(),
    )
    .run();
}

export async function listLogs(
  db: D1Database,
  limit = 50,
  offset = 0,
): Promise<unknown[]> {
  const res = await db
    .prepare(`SELECT * FROM logs ORDER BY created_at DESC LIMIT ? OFFSET ?`)
    .bind(limit, offset)
    .all();
  return res.results ?? [];
}
