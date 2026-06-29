/** Public install/landing routes — NO AUTH. Served from terragravity.cloud.
 *
 * Assets are embedded as strings by scripts/embed-web.mjs (run before deploy),
 * which reads web/ and regenerates web-assets.ts. This keeps the Worker
 * self-contained (no KV/R2 fetch on the hot path for the landing page).
 */
import { Hono } from "hono";
import type { Env } from "./lib/types";
import { INDEX_HTML, INSTALL_SH, INSTALL_PS1, LAUNCHER_PY } from "./web-assets";

export const web = new Hono<{ Bindings: Env }>();

const SH_HEADERS = { "content-type": "text/x-shellscript; charset=utf-8", "cache-control": "public, max-age=300" };
const PS_HEADERS = { "content-type": "text/plain; charset=utf-8", "cache-control": "public, max-age=300" };
const PY_HEADERS = { "content-type": "text/x-python; charset=utf-8", "cache-control": "public, max-age=300" };
const HTML_HEADERS = { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300" };

web.get("/", (c) => c.body(INDEX_HTML, 200, HTML_HEADERS));
web.get("/install.sh", (c) => c.body(INSTALL_SH, 200, SH_HEADERS));
web.get("/install.ps1", (c) => c.body(INSTALL_PS1, 200, PS_HEADERS));
web.get("/launcher.py", (c) => c.body(LAUNCHER_PY, 200, PY_HEADERS));
