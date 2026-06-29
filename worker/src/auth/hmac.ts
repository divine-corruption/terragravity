/** HMAC request signing for upstream calls to the Studio FastAPI.
 *
 * MUST match studio/app/auth.py sign():
 *   msg = `${timestamp}\n${method}\n${path}\n${body}`
 *   signature = hex(HMAC_SHA256(secret, msg))
 */

function toHex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function signUpstream(
  timestamp: string,
  method: string,
  path: string,
  body: string,
  secret: string,
): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const msg = `${timestamp}\n${method}\n${path}\n${body}`;
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg));
  return toHex(sig);
}

/** Build the headers the Studio expects for a signed POST. */
export async function signedHeaders(
  method: string,
  path: string,
  body: string,
  secret: string,
): Promise<Record<string, string>> {
  const ts = String(Math.floor(Date.now() / 1000));
  const sig = await signUpstream(ts, method, path, body, secret);
  return {
    "Content-Type": "application/json",
    "X-Timestamp": ts,
    "X-Signature": sig,
  };
}
