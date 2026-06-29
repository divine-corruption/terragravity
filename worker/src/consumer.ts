/** Queue consumer — drains job messages and forwards to the Studio FastAPI.
 *
 * Exported as the Worker's `queue` handler. On success/failure it updates the
 * D1 job row so /status polling reflects reality. Failed messages are retried
 * by the Queues runtime (max_retries in wrangler.toml), then dead-lettered.
 */
import { updateJob, writeLog } from "./db/d1";
import { callStudio } from "./lib/upstream";
import type { Env, JobMessage } from "./lib/types";

const PATH_FOR: Record<string, string> = {
  chat: "/chat",
  agent: "/execute",
  deploy: "/execute",
  memory: "/memory",
  tasks: "/execute",
};

export async function handleQueue(
  batch: MessageBatch<JobMessage>,
  env: Env,
): Promise<void> {
  for (const message of batch.messages) {
    const job = message.body;
    try {
      await updateJob(env.DB, job.job_id, { status: "running" });
      const path = PATH_FOR[job.type] ?? "/execute";
      const res = await callStudio(env, path, {
        prompt: job.prompt,
        job_id: job.job_id,
        session_id: job.session_id,
        request_uuid: job.request_uuid,
      });

      if (res.ok) {
        const body = res.body as Record<string, unknown>;
        await updateJob(env.DB, job.job_id, {
          status: "done",
          response: typeof body.response === "string" ? body.response : JSON.stringify(body),
          exec_ms: typeof body.exec_ms === "number" ? body.exec_ms : undefined,
          tokens_in: typeof body.tokens_in === "number" ? body.tokens_in : undefined,
          tokens_out: typeof body.tokens_out === "number" ? body.tokens_out : undefined,
        });
        await writeLog(env.DB, {
          request_uuid: job.request_uuid,
          user_id: job.user_id,
          route: `queue:${job.type}`,
          status: 200,
        });
        message.ack();
      } else {
        throw new Error(`upstream ${res.status}: ${JSON.stringify(res.body)}`);
      }
    } catch (e) {
      await updateJob(env.DB, job.job_id, { status: "error", error: String(e) });
      await writeLog(env.DB, {
        request_uuid: job.request_uuid,
        user_id: job.user_id,
        route: `queue:${job.type}`,
        status: 500,
        error: String(e),
      });
      // Let the runtime retry (don't ack) until max_retries, then DLQ.
      message.retry();
    }
  }
}
