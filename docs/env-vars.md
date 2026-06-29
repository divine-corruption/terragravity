# Environment Variables & Secrets

Two halves, two secret stores. **Never commit secrets.** The shared
`GATEWAY_HMAC_SECRET` MUST be identical on both sides.

## Worker (Cloudflare)

### Vars (non-secret) — in `wrangler.toml [vars]`
| Name | Example | Meaning |
|------|---------|---------|
| `STUDIO_URL` | `https://studio.yourdomain.com` | Cloudflare Tunnel hostname for FastAPI |
| `R2_URL_TTL_S` | `900` | Signed download URL lifetime (seconds) |
| `RATE_LIMIT_PER_MIN` | `60` | Per-API-key per-route request cap |

### Secrets — set via `wrangler secret put NAME`
| Name | Meaning |
|------|---------|
| `JWT_SECRET` | HS256 signing key for session JWTs |
| `API_KEY_SALT` | Salt for hashing API keys before D1 comparison |
| `GATEWAY_HMAC_SECRET` | Shared secret for Worker→Studio request signing |

### Bindings — in `wrangler.toml`
`DB` (D1) · `KV` · `R2` · `JOBS_QUEUE` (producer) + consumer on `terragravity-jobs`.

## Studio (FastAPI in Lightning)

Set in the Studio's environment (e.g. `~/.hermes`-adjacent `.env`, or export
before launching uvicorn):

| Name | Required | Meaning |
|------|----------|---------|
| `GATEWAY_HMAC_SECRET` | **yes (prod)** | Must equal the Worker's secret |
| `GATEWAY_MAX_SKEW_S` | no (default 300) | Max timestamp skew for signed requests |
| `GATEWAY_DEV_INSECURE` | no | `1` bypasses HMAC — **local dev only** |
| `HERMES_BIN` | no (default `hermes`) | Path to the hermes binary |
| `HERMES_TIMEOUT_S` | no (default 600) | Max seconds for a hermes call |

## Generating strong secrets

```bash
openssl rand -hex 32   # for JWT_SECRET / API_KEY_SALT / GATEWAY_HMAC_SECRET
```
