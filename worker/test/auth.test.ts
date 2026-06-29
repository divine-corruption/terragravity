/** Unit tests for auth primitives. These run in plain Node (WebCrypto is
 *  available as globalThis.crypto) — no Workers runtime needed. */
import { describe, expect, it } from "vitest";
import { mintJwt, verifyJwt } from "../src/auth/jwt";
import { hashApiKey, safeEqual } from "../src/auth/apikey";
import { signUpstream } from "../src/auth/hmac";

const SECRET = "unit-test-secret";

describe("jwt", () => {
  it("mints and verifies a valid token", async () => {
    const tok = await mintJwt({ sub: "u1", role: "user", jti: "j1" }, SECRET, 60);
    const claims = await verifyJwt(tok, SECRET);
    expect(claims).not.toBeNull();
    expect(claims?.sub).toBe("u1");
    expect(claims?.role).toBe("user");
  });

  it("rejects a token signed with a different secret", async () => {
    const tok = await mintJwt({ sub: "u1", role: "user", jti: "j1" }, SECRET, 60);
    expect(await verifyJwt(tok, "wrong-secret")).toBeNull();
  });

  it("rejects an expired token", async () => {
    const tok = await mintJwt({ sub: "u1", role: "user", jti: "j1" }, SECRET, -10);
    expect(await verifyJwt(tok, SECRET)).toBeNull();
  });

  it("rejects a malformed token", async () => {
    expect(await verifyJwt("not.a.jwt", SECRET)).toBeNull();
  });
});

describe("apikey", () => {
  it("hashes deterministically with salt", async () => {
    const a = await hashApiKey("rawkey", "salt");
    const b = await hashApiKey("rawkey", "salt");
    expect(a).toBe(b);
    expect(a).toHaveLength(64); // sha256 hex
  });

  it("different salt -> different hash", async () => {
    const a = await hashApiKey("rawkey", "salt1");
    const b = await hashApiKey("rawkey", "salt2");
    expect(a).not.toBe(b);
  });

  it("safeEqual works", () => {
    expect(safeEqual("abc", "abc")).toBe(true);
    expect(safeEqual("abc", "abd")).toBe(false);
    expect(safeEqual("abc", "abcd")).toBe(false);
  });
});

describe("hmac upstream signing (cross-language contract)", () => {
  it("produces the documented signature for a known vector", async () => {
    // This vector is also asserted on the Python side (studio test) to prove
    // the Worker and FastAPI agree byte-for-byte.
    const ts = "1700000000";
    const method = "POST";
    const path = "/chat";
    const body = '{"prompt":"hi"}';
    const sig = await signUpstream(ts, method, path, body, "shared");
    // Precomputed HMAC-SHA256 of "1700000000\nPOST\n/chat\n{\"prompt\":\"hi\"}"
    // with key "shared". Computed independently (see studio cross-check test).
    expect(sig).toMatch(/^[0-9a-f]{64}$/);
    expect(sig).toBe(KNOWN_VECTOR);
  });
});

// Filled in by the cross-check step (computed once, asserted on both sides).
const KNOWN_VECTOR = "a7edc015199788fd06256f3d09e686e658a81410289f31873d7947ee755c9c24";
