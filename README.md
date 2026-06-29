# Terragravity

**A production-grade edge gateway to talk to a Hermes agent (running in Lightning AI) from anywhere.**

Cloudflare Worker (edge) ⟶ Cloudflare Queue ⟶ FastAPI (beside Hermes in Lightning Studio, via Cloudflare Tunnel).

```
client ──HTTPS──▶ Worker (auth, rate-limit, enqueue) ──▶ Queue ──▶ Consumer ──Tunnel──▶ FastAPI ──▶ Hermes
                      │                                                                    │
                   D1 · KV · R2                                                      hermes chat -q
```

## Why this shape

- **Worker = the only public surface.** It authenticates (API key + JWT + HMAC), rate-limits, persists to D1, and drops long work on a Queue, returning a **Job ID immediately**. No request hangs waiting on a slow agent.
- **Queue consumer** forwards jobs to the Studio and writes results back to D1, so clients **poll `/status`**.
- **Cloudflare Tunnel** gives the Lightning Studio a stable hostname with **no inbound ports** — solving the "Lightning has no public IP" problem.
- **R2** stores generated artifacts; clients get **signed download URLs**.
- **Notifier** layer (Discord / email / generic webhook) is channel-agnostic — plug your own messaging in via the webhook adapter.

## Repo layout

```
worker/   Cloudflare Worker (TypeScript, Hono) — edge API + queue consumer
studio/   FastAPI server that runs beside Hermes in the Lightning Studio
docs/     architecture, deployment, env vars, OpenAPI
.github/  CI (typecheck + tests on both halves)
scripts/  dev + deploy helpers
```

## Endpoints (edge Worker)

| Method | Path | Notes |
|--------|------|-------|
| POST | /chat | enqueue chat → `{job_id, status}` 202 |
| POST | /agent | enqueue agent task → 202 |
| POST | /deploy | enqueue deploy task → 202 |
| POST | /status | `{job_id}` → job row from D1 |
| POST | /cancel | signal cancel upstream |
| POST | /memory | proxy to Hermes memory |
| POST | /tasks | list recent jobs |
| GET  | /logs | paginated request logs |
| GET  | /health | edge + upstream health |

All except `/health` require `X-API-Key` (and optionally `Authorization: Bearer <jwt>`).

## Quick start (local dev)

```bash
# Studio (FastAPI) — insecure local mode bypasses HMAC for dev only
cd studio
pip install -r requirements.txt
GATEWAY_DEV_INSECURE=1 uvicorn app.main:app --port 8088 --reload
PYTHONPATH=. pytest -q          # 7 tests

# Worker
cd ../worker
npm install
npm run typecheck               # tsc clean
npm test                        # 16 vitest tests
npx wrangler dev                # local edge (needs D1/KV/R2/Queue bindings)
```

## Deploy

See **docs/deployment.md** (Cloudflare resources + Tunnel + secrets) and
**docs/env-vars.md** (every variable). Short version:

```bash
# 1. Create CF resources
wrangler d1 create terragravity
wrangler kv namespace create KV
wrangler r2 bucket create terragravity-artifacts
wrangler queues create terragravity-jobs
# 2. Put the IDs in wrangler.toml, then migrate
npm run migrate:remote
# 3. Secrets (never commit these)
wrangler secret put JWT_SECRET
wrangler secret put API_KEY_SALT
wrangler secret put GATEWAY_HMAC_SECRET
# 4. Tunnel from the Studio (see deployment.md), then
wrangler deploy
```

## Security

API key (salted SHA-256 in D1) · JWT HS256 (WebCrypto) · HMAC request signing
(Worker↔Studio, timestamp-bound + replay nonce) · KV rate limiting · PIN/identity
gate for command channels. The Worker↔Studio HMAC contract is locked by a
shared known-vector test on **both** sides (`worker/test/auth.test.ts` ==
`studio/tests/test_hmac_contract.py`).

## Status

Built & tested (staging): studio API, worker, auth, queue, notifier — all green.
Pending live deploy: Cloudflare resources, Tunnel, end-to-end trace.
