/** Shared types + Env bindings for the Terragravity Worker. */

export interface Env {
  DB: D1Database;
  KV: KVNamespace;
  R2: R2Bucket;
  JOBS_QUEUE: Queue<JobMessage>;
  // vars
  STUDIO_URL: string;
  R2_URL_TTL_S: string;
  RATE_LIMIT_PER_MIN: string;
  // secrets
  JWT_SECRET: string;
  API_KEY_SALT: string;
  GATEWAY_HMAC_SECRET: string;
}

export type JobType =
  | "chat"
  | "agent"
  | "deploy"
  | "memory"
  | "tasks";

export type JobStatus =
  | "queued"
  | "running"
  | "done"
  | "error"
  | "cancelled";

export interface JobMessage {
  job_id: string;
  user_id: string;
  type: JobType;
  prompt: string;
  session_id?: string;
  request_uuid: string;
}

export interface AuthContext {
  user_id: string;
  role: string;
  jti: string;
}
