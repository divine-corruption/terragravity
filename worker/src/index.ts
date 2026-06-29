/** Terragravity edge Worker — public API surface (Hono).
 *
 * Auth on every route. Long jobs are enqueued (return Job ID immediately);
 * quick reads hit D1 directly. The queue consumer (consumer.ts) forwards
 * queued jobs to the Studio FastAPI over the Tunnel.
 */
import { Hono } from "hono";
import { authMiddleware } from "./middleware";
import { createJob, getJob, listLogs, uuid, writeLog } from "./db/d1";
import { callStudio } from "./lib/upstream";
import type { Env, JobMessage, JobType } from "./lib/types";
import { web } from "./web";

const app = new Hono<{ Bindings: Env }>();

// ── Public install / landing pages (no auth) ─────────────────────────
//   GET /            → landing page (OS auto-detect + install one-liner)
//   GET /install.sh  → macOS/Linux installer
//   GET /install.ps1 → Windows installer
//   GET /launcher.py → the tg launcher client
app.route("/", web);

// ── Public health (no auth) ──────────────────────────────────────────
app.get("/health", async (c) => {
  const upstream = await callStudio(c.env, "/health", {}).catch(() => null);
  return c.json({
    status: "ok",
    edge: true,
    upstream_reachable: !!upstream?.ok,
    upstream_status: upstream?.status ?? null,
  });
});

// ── Everything below requires auth ───────────────────────────────────
app.use("/chat", authMiddleware);
app.use("/agent", authMiddleware);
app.use("/deploy", authMiddleware);
app.use("/status", authMiddleware);
app.use("/cancel", authMiddleware);
app.use("/memory", authMiddleware);
app.use("/tasks", authMiddleware);
app.use("/logs", authMiddleware);

async function enqueue(
  c: any,
  type: JobType,
  prompt: string,
  session_id?: string,
): Promise<Response> {
  const auth = c.get("auth");
  const request_uuid = c.get("request_uuid");
  const job_id = uuid();
  await createJob(c.env.DB, { id: job_id, user_id: auth.user_id, type, prompt });
  const msg: JobMessage = {
    job_id,
    user_id: auth.user_id,
    type,
    prompt,
    session_id,
    request_uuid,
  };
  await c.env.JOBS_QUEUE.send(msg);
  await writeLog(c.env.DB, {
    request_uuid,
    user_id: auth.user_id,
    route: c.req.path,
    status: 202,
  });
  return c.json({ job_id, status: "queued" }, 202);
}

app.post("/chat", async (c) => {
  const { prompt, session_id } = await c.req.json<{ prompt: string; session_id?: string }>();
  if (!prompt) return c.json({ error: "prompt required" }, 400);
  return enqueue(c, "chat", prompt, session_id);
});

app.post("/agent", async (c) => {
  const { prompt, session_id } = await c.req.json<{ prompt: string; session_id?: string }>();
  if (!prompt) return c.json({ error: "prompt required" }, 400);
  return enqueue(c, "agent", prompt, session_id);
});

app.post("/deploy", async (c) => {
  const { target } = await c.req.json<{ target?: string }>().catch(() => ({ target: undefined }));
  return enqueue(c, "deploy", `deploy ${target ?? ""}`.trim());
});

app.post("/status", async (c) => {
  const { job_id } = await c.req.json<{ job_id?: string }>().catch(() => ({ job_id: undefined }));
  if (!job_id) return c.json({ error: "job_id required" }, 400);
  const job = await getJob(c.env.DB, job_id);
  if (!job) return c.json({ error: "not found" }, 404);
  return c.json(job);
});

app.post("/cancel", async (c) => {
  const { job_id } = await c.req.json<{ job_id: string }>();
  if (!job_id) return c.json({ error: "job_id required" }, 400);
  const res = await callStudio(c.env, "/cancel", { job_id });
  return c.json(res.body, res.ok ? 200 : 502);
});

app.post("/memory", async (c) => {
  const payload = await c.req.json().catch(() => ({}));
  const res = await callStudio(c.env, "/memory", payload);
  return c.json(res.body, res.ok ? 200 : 502);
});

app.post("/tasks", async (c) => {
  // List or create tasks (jobs of type agent/deploy). Minimal: list recent.
  const auth = c.get("auth");
  const res = await c.env.DB.prepare(
    `SELECT id, type, status, created_at FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 50`,
  )
    .bind(auth.user_id)
    .all();
  return c.json({ tasks: res.results ?? [] });
});

app.get("/logs", async (c) => {
  const limit = parseInt(c.req.query("limit") || "50", 10);
  const offset = parseInt(c.req.query("offset") || "0", 10);
  const rows = await listLogs(c.env.DB, limit, offset);
  return c.json({ logs: rows });
});

// Combine the Hono fetch handler with the Queue consumer in one Worker.
import { handleQueue } from "./consumer";

export default {
  fetch: app.fetch,
  async queue(batch: MessageBatch<JobMessage>, env: Env): Promise<void> {
    await handleQueue(batch, env);
  },
};
