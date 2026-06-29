-- Terragravity D1 schema (migration 0001)
-- All ids are UUID text. Timestamps are unix epoch (INTEGER seconds).

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  phone         TEXT UNIQUE,
  pin_hash      TEXT,
  api_key_hash  TEXT UNIQUE,
  role          TEXT NOT NULL DEFAULT 'user',
  created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  jwt_id      TEXT NOT NULL,
  created_at  INTEGER NOT NULL,
  expires_at  INTEGER NOT NULL,
  revoked     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS jobs (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  type        TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'queued',
  prompt      TEXT,
  response    TEXT,
  error       TEXT,
  tokens_in   INTEGER,
  tokens_out  INTEGER,
  exec_ms     INTEGER,
  r2_key      TEXT,
  created_at  INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

CREATE TABLE IF NOT EXISTS messages (
  id          TEXT PRIMARY KEY,
  job_id      TEXT NOT NULL REFERENCES jobs(id),
  role        TEXT NOT NULL,
  content     TEXT NOT NULL,
  created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_job ON messages(job_id);

CREATE TABLE IF NOT EXISTS projects (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  name        TEXT NOT NULL,
  repo        TEXT,
  r2_prefix   TEXT,
  created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
  id            TEXT PRIMARY KEY,
  request_uuid  TEXT NOT NULL,
  user_id       TEXT,
  route         TEXT NOT NULL,
  status        INTEGER NOT NULL,
  exec_ms       INTEGER,
  tokens        INTEGER,
  error         TEXT,
  created_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_uuid ON logs(request_uuid);
CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at);

CREATE TABLE IF NOT EXISTS memory (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  key         TEXT NOT NULL,
  value       TEXT,
  updated_at  INTEGER NOT NULL,
  UNIQUE(user_id, key)
);
