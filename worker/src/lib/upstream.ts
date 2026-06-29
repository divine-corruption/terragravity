/** Client for calling the Studio FastAPI over the Cloudflare Tunnel. */
import { signedHeaders } from "../auth/hmac";
import type { Env } from "./types";

export interface UpstreamResult {
  ok: boolean;
  status: number;
  body: unknown;
}

export async function callStudio(
  env: Env,
  path: string,
  payload: unknown,
): Promise<UpstreamResult> {
  const body = JSON.stringify(payload ?? {});
  const headers = await signedHeaders("POST", path, body, env.GATEWAY_HMAC_SECRET);
  const url = `${env.STUDIO_URL.replace(/\/$/, "")}${path}`;
  try {
    const resp = await fetch(url, { method: "POST", headers, body });
    let parsed: unknown;
    const text = await resp.text();
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = { raw: text };
    }
    return { ok: resp.ok, status: resp.status, body: parsed };
  } catch (e) {
    return { ok: false, status: 502, body: { error: String(e) } };
  }
}
