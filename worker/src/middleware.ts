/** Auth middleware: API key -> JWT -> rate limit. Attaches AuthContext. */
import type { Context, Next } from "hono";
import { hashApiKey, safeEqual } from "./auth/apikey";
import { verifyJwt } from "./auth/jwt";
import { rateLimit } from "./auth/ratelimit";
import type { AuthContext, Env } from "./lib/types";

export async function authMiddleware(
  c: Context<{ Bindings: Env }>,
  next: Next,
): Promise<Response | void> {
  // request UUID for logging/tracing
  c.set("request_uuid", crypto.randomUUID());

  // 1) API key required
  const apiKey = c.req.header("X-API-Key");
  if (!apiKey) return c.json({ error: "missing X-API-Key" }, 401);
  const keyHash = await hashApiKey(apiKey, c.env.API_KEY_SALT);
  const user = await c.env.DB.prepare(
    `SELECT id, role, api_key_hash FROM users WHERE api_key_hash = ?`,
  )
    .bind(keyHash)
    .first<{ id: string; role: string; api_key_hash: string }>();
  if (!user || !safeEqual(user.api_key_hash, keyHash)) {
    return c.json({ error: "invalid API key" }, 401);
  }

  // 2) JWT optional-but-verified if present (for session-scoped calls)
  const authz = c.req.header("Authorization");
  let jti = "apikey";
  if (authz?.startsWith("Bearer ")) {
    const claims = await verifyJwt(authz.slice(7), c.env.JWT_SECRET);
    if (!claims) return c.json({ error: "invalid or expired JWT" }, 401);
    // JWT denylist (revoked sessions)
    if (await c.env.KV.get(`jwt_deny:${claims.jti}`)) {
      return c.json({ error: "session revoked" }, 401);
    }
    jti = claims.jti;
  }

  // 3) rate limit per API-key user + route
  const perMin = parseInt(c.env.RATE_LIMIT_PER_MIN || "60", 10);
  const rl = await rateLimit(c.env.KV, user.id, c.req.path, perMin);
  c.header("X-RateLimit-Remaining", String(rl.remaining));
  if (!rl.allowed) {
    return c.json({ error: "rate limited", reset_s: rl.resetSeconds }, 429);
  }

  c.set("auth", { user_id: user.id, role: user.role, jti });
  await next();
}
