import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DiscordNotifier,
  EmailNotifier,
  NotifierDispatcher,
  WebhookNotifier,
  type Notification,
} from "../src/notify/notifier";

const note: Notification = {
  title: "Job done",
  body: "Build finished",
  level: "success",
  job_id: "abc123",
  url: "https://r2.example/out.txt",
};

afterEach(() => vi.restoreAllMocks());

function mockFetch(ok: boolean, status = 200) {
  const fn = vi.fn(
    async (_url: string | URL | Request, _init?: RequestInit): Promise<Response> =>
      new Response(ok ? "{}" : "err", { status }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("DiscordNotifier", () => {
  it("posts an embed and reports ok", async () => {
    const fetchFn = mockFetch(true);
    const r = await new DiscordNotifier("https://discord/webhook").send(note);
    expect(r.ok).toBe(true);
    expect(fetchFn).toHaveBeenCalledOnce();
    const [, init] = fetchFn.mock.calls[0];
    const payload = JSON.parse((init as RequestInit).body as string);
    expect(payload.embeds[0].title).toBe("Job done");
    expect(payload.embeds[0].fields.some((f: any) => f.value === "abc123")).toBe(true);
  });

  it("returns error when no webhook url", async () => {
    const r = await new DiscordNotifier("").send(note);
    expect(r.ok).toBe(false);
  });

  it("propagates non-2xx as error", async () => {
    mockFetch(false, 500);
    const r = await new DiscordNotifier("https://discord/webhook").send(note);
    expect(r.ok).toBe(false);
    expect(r.error).toContain("500");
  });
});

describe("WebhookNotifier", () => {
  it("signs the body with HMAC when a secret is set", async () => {
    const fetchFn = mockFetch(true);
    const r = await new WebhookNotifier("https://my/custom", "sekret").send(note);
    expect(r.ok).toBe(true);
    const [, init] = fetchFn.mock.calls[0];
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers["X-Signature"]).toMatch(/^[0-9a-f]{64}$/);
  });

  it("omits signature when no secret", async () => {
    const fetchFn = mockFetch(true);
    await new WebhookNotifier("https://my/custom").send(note);
    const [, init] = fetchFn.mock.calls[0];
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers["X-Signature"]).toBeUndefined();
  });
});

describe("EmailNotifier", () => {
  it("builds a subject with level + title", async () => {
    const fetchFn = mockFetch(true);
    await new EmailNotifier("https://email/api", "k", "a@x.com", "b@x.com").send(note);
    const [, init] = fetchFn.mock.calls[0];
    const payload = JSON.parse((init as RequestInit).body as string);
    expect(payload.subject).toBe("[success] Job done");
    expect(payload.text).toContain("https://r2.example/out.txt");
  });

  it("errors when unconfigured", async () => {
    const r = await new EmailNotifier("", "", "", "").send(note);
    expect(r.ok).toBe(false);
  });
});

describe("NotifierDispatcher", () => {
  it("fans out to all channels and never throws on one failure", async () => {
    mockFetch(true);
    const good = new DiscordNotifier("https://d/w");
    const bad = {
      name: "explode",
      send: async () => {
        throw new Error("boom");
      },
    };
    const disp = new NotifierDispatcher([good, bad as any]);
    const res = await disp.dispatch(note);
    expect(res.discord.ok).toBe(true);
    expect(res.explode.ok).toBe(false);
    expect(res.explode.error).toContain("boom");
  });
});
