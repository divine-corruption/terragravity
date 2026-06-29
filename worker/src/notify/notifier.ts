/** Channel-agnostic notification layer.
 *
 * A Notifier delivers a Notification to one channel. The dispatcher fans a
 * notification out to all configured channels and never throws — a failing
 * channel is logged and skipped so one bad webhook can't break a job.
 *
 * Your custom messaging solution implements `Notifier` (or just uses the
 * generic WebhookNotifier) — no other code changes needed.
 */

export interface Notification {
  title: string;
  body: string;
  level: "info" | "success" | "warn" | "error";
  job_id?: string;
  url?: string; // e.g. R2 signed URL to full output
}

export interface Notifier {
  readonly name: string;
  send(n: Notification): Promise<{ ok: boolean; error?: string }>;
}

/** Discord incoming-webhook adapter. */
export class DiscordNotifier implements Notifier {
  readonly name = "discord";
  constructor(private webhookUrl: string) {}

  async send(n: Notification): Promise<{ ok: boolean; error?: string }> {
    if (!this.webhookUrl) return { ok: false, error: "no webhook url" };
    const color = { info: 0x3498db, success: 0x2ecc71, warn: 0xf1c40f, error: 0xe74c3c }[
      n.level
    ];
    const payload = {
      embeds: [
        {
          title: n.title,
          description: n.body.slice(0, 4000),
          color,
          fields: [
            ...(n.job_id ? [{ name: "Job", value: n.job_id, inline: true }] : []),
            ...(n.url ? [{ name: "Output", value: n.url }] : []),
          ],
        },
      ],
    };
    try {
      const r = await fetch(this.webhookUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return { ok: r.ok, error: r.ok ? undefined : `discord ${r.status}` };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }
}

/** Generic webhook adapter — POSTs the raw Notification JSON.
 *  This is the integration point for your custom messaging service. */
export class WebhookNotifier implements Notifier {
  readonly name = "webhook";
  constructor(
    private url: string,
    private secret?: string,
  ) {}

  async send(n: Notification): Promise<{ ok: boolean; error?: string }> {
    if (!this.url) return { ok: false, error: "no url" };
    const body = JSON.stringify(n);
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.secret) {
      const key = await crypto.subtle.importKey(
        "raw",
        new TextEncoder().encode(this.secret),
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"],
      );
      const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
      headers["X-Signature"] = [...new Uint8Array(sig)]
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    }
    try {
      const r = await fetch(this.url, { method: "POST", headers, body });
      return { ok: r.ok, error: r.ok ? undefined : `webhook ${r.status}` };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }
}

/** Email via an HTTP email API (e.g. MailChannels/Resend-style POST).
 *  Kept transport-simple so it works from a Worker without SMTP sockets. */
export class EmailNotifier implements Notifier {
  readonly name = "email";
  constructor(
    private apiUrl: string,
    private apiKey: string,
    private from: string,
    private to: string,
  ) {}

  async send(n: Notification): Promise<{ ok: boolean; error?: string }> {
    if (!this.apiUrl || !this.to) return { ok: false, error: "email not configured" };
    const payload = {
      from: this.from,
      to: this.to,
      subject: `[${n.level}] ${n.title}`,
      text: `${n.body}${n.url ? `\n\n${n.url}` : ""}`,
    };
    try {
      const r = await fetch(this.apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify(payload),
      });
      return { ok: r.ok, error: r.ok ? undefined : `email ${r.status}` };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }
}

/** Fan-out dispatcher — sends to all channels, collects results, never throws. */
export class NotifierDispatcher {
  constructor(private channels: Notifier[]) {}

  async dispatch(n: Notification): Promise<Record<string, { ok: boolean; error?: string }>> {
    const out: Record<string, { ok: boolean; error?: string }> = {};
    await Promise.all(
      this.channels.map(async (ch) => {
        try {
          out[ch.name] = await ch.send(n);
        } catch (e) {
          out[ch.name] = { ok: false, error: String(e) };
        }
      }),
    );
    return out;
  }
}
