/** KV-backed sliding-window rate limiter (per key + route). */

export interface RateResult {
  allowed: boolean;
  remaining: number;
  resetSeconds: number;
}

/**
 * Fixed-window limiter keyed by `rl:{id}:{route}:{minuteBucket}`.
 * Simple, cheap, and adequate for per-API-key throttling at the edge.
 */
export async function rateLimit(
  kv: KVNamespace,
  id: string,
  route: string,
  perMinute: number,
): Promise<RateResult> {
  const now = Math.floor(Date.now() / 1000);
  const bucket = Math.floor(now / 60);
  const key = `rl:${id}:${route}:${bucket}`;
  const current = parseInt((await kv.get(key)) || "0", 10);
  if (current >= perMinute) {
    return { allowed: false, remaining: 0, resetSeconds: 60 - (now % 60) };
  }
  await kv.put(key, String(current + 1), { expirationTtl: 90 });
  return {
    allowed: true,
    remaining: perMinute - current - 1,
    resetSeconds: 60 - (now % 60),
  };
}

/** Replay protection: store a nonce once; reject if seen. */
export async function checkNonce(kv: KVNamespace, nonce: string): Promise<boolean> {
  const key = `nonce:${nonce}`;
  if (await kv.get(key)) return false;
  await kv.put(key, "1", { expirationTtl: 600 });
  return true;
}
