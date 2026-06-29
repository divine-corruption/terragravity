/** API-key hashing + verification. Keys are stored hashed in D1. */

function toHex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Salted SHA-256 of the raw API key. */
export async function hashApiKey(rawKey: string, salt: string): Promise<string> {
  const data = new TextEncoder().encode(`${salt}:${rawKey}`);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return toHex(digest);
}

/** Constant-time compare of two hex strings. */
export function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
