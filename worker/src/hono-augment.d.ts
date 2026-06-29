/** Hono context variable augmentation (kept separate so it doesn't disrupt
 *  relative-module resolution in the file that uses it). */
import type { AuthContext } from "./lib/types";

declare module "hono" {
  interface ContextVariableMap {
    auth: AuthContext;
    request_uuid: string;
  }
}
