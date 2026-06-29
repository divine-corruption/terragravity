# Deployment Guide

Prereqs: a Cloudflare account on a **paid Workers plan** (for Queues), a domain
on Cloudflare, `wrangler` logged in (`wrangler login`), and SSH to the Lightning
Studio running Hermes.

## 1. Create Cloudflare resources

```bash
cd worker
wrangler d1 create terragravity              # copy database_id -> wrangler.toml
wrangler kv namespace create KV              # copy id -> wrangler.toml
wrangler r2 bucket create terragravity-artifacts
wrangler queues create terragravity-jobs
wrangler queues create terragravity-jobs-dlq
```

Paste the returned IDs into `wrangler.toml` (replace the PLACEHOLDER values).

## 2. Apply the D1 schema

```bash
npm run migrate:remote     # wrangler d1 migrations apply terragravity --remote
```

## 3. Set secrets (both sides must share GATEWAY_HMAC_SECRET)

```bash
# generate once
HMAC=$(openssl rand -hex 32)

# Worker
printf '%s' "$HMAC" | wrangler secret put GATEWAY_HMAC_SECRET
openssl rand -hex 32 | wrangler secret put JWT_SECRET
openssl rand -hex 32 | wrangler secret put API_KEY_SALT
```

On the Studio, export the SAME `GATEWAY_HMAC_SECRET` before launching FastAPI.

## 4. Cloudflare Tunnel (Studio → FastAPI)

On the Lightning Studio:

```bash
# install cloudflared (linux amd64)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared && sudo mv cloudflared /usr/local/bin/

cloudflared tunnel login
cloudflared tunnel create terragravity-studio
# route a hostname (must be a zone on your CF account)
cloudflared tunnel route dns terragravity-studio studio.yourdomain.com
```

Use the provided `studio/cloudflared/config.yml` template (set the tunnel UUID
and credentials path), then run FastAPI + the tunnel:

```bash
cd studio
GATEWAY_HMAC_SECRET="$HMAC" uvicorn app.main:app --host 127.0.0.1 --port 8088 &
cloudflared tunnel --config studio/cloudflared/config.yml run terragravity-studio &
```

Set `STUDIO_URL = "https://studio.yourdomain.com"` in `wrangler.toml [vars]`.

## 5. Deploy the Worker

```bash
cd worker
wrangler deploy
```

## 6. Seed a user (API key)

```bash
# hash an API key with your salt, insert into D1
RAW=$(openssl rand -hex 24)
# compute salted sha256 the same way the Worker does:
HASH=$(node -e "const s=process.argv[1],k=process.argv[2];crypto.subtle.digest('SHA-256',new TextEncoder().encode(s+':'+k)).then(d=>console.log([...new Uint8Array(d)].map(b=>b.toString(16).padStart(2,'0')).join('')))" "$API_KEY_SALT" "$RAW")
wrangler d1 execute terragravity --remote --command \
  "INSERT INTO users (id, api_key_hash, role, created_at) VALUES ('$(uuidgen)', '$HASH', 'admin', strftime('%s','now'))"
echo "Your API key: $RAW"   # store it; only the hash is in D1
```

## 7. Verify end-to-end

```bash
curl https://your-worker.workers.dev/health
curl -X POST https://your-worker.workers.dev/chat \
  -H "X-API-Key: $RAW" -H "Content-Type: application/json" \
  -d '{"prompt":"say hello"}'         # -> {job_id, status:queued}
curl -X POST https://your-worker.workers.dev/status \
  -H "X-API-Key: $RAW" -d '{"job_id":"<id>"}'   # poll until done
```
