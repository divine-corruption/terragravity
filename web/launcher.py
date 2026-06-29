#!/usr/bin/env python3
"""Terragravity Hermes launcher.

A tiny, dependency-free (stdlib-only) client for the Terragravity edge gateway.
Talks to the Cloudflare Worker over HTTPS, authenticating with an API key.

Commands:
  tg health                 # check edge + upstream
  tg chat [message...]      # one-shot chat, or interactive REPL if no message
  tg agent <task...>        # enqueue an agent task, poll to completion
  tg status <job_id>        # check a job
  tg logs [--limit N]       # recent request logs

Config comes from environment (the `tg` wrapper sources ~/.terragravity/config.env):
  TG_GATEWAY   gateway base URL (e.g. https://api.terragravity.cloud)
  TG_API_KEY   your API key
"""
import json
import os
import sys
import time
import typing
import urllib.request
import urllib.error

GATEWAY = os.environ.get("TG_GATEWAY", "https://api.terragravity.cloud").rstrip("/")
API_KEY = os.environ.get("TG_API_KEY", "").strip()
POLL_INTERVAL = 2.0
POLL_TIMEOUT = 600  # 10 min


def _req(method, path, body=None, auth=True, timeout=30):
    url = GATEWAY + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if auth:
        if not API_KEY:
            die("No API key set. Edit ~/.terragravity/config.env and set TG_API_KEY.")
        headers["X-API-Key"] = API_KEY
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw[:300]}
    except urllib.error.URLError as e:
        die(f"Cannot reach gateway {GATEWAY}: {e.reason}")
    except Exception as e:
        die(f"Request failed: {e}")


def die(msg, code=1) -> typing.NoReturn:
    sys.stderr.write(f"\033[1;31m✗ {msg}\033[0m\n")
    sys.exit(code)


def info(msg):
    sys.stderr.write(f"\033[1;36m›\033[0m {msg}\n")


def cmd_health(_args):
    status, body = _req("GET", "/health", auth=False)
    print(json.dumps(body, indent=2))
    return 0 if status == 200 and body.get("status") == "ok" else 1


def _enqueue_and_wait(kind, prompt, session_id=None):
    payload = {"prompt": prompt}
    if session_id:
        payload["session_id"] = session_id
    status, body = _req("POST", f"/{kind}", payload)
    if status != 202:
        die(f"enqueue failed ({status}): {body.get('error', body)}")
    job_id = body.get("job_id")
    if not job_id:
        die(f"no job_id returned: {body}")
    info(f"queued job {job_id} — polling…")
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        st, jb = _req("POST", "/status", {"job_id": job_id})
        state = jb.get("status")
        if state in ("done", "completed", "succeeded"):
            return jb.get("result") or jb.get("output") or jb.get("response") or jb
        if state in ("failed", "error", "cancelled"):
            die(f"job {state}: {jb.get('error', jb)}")
    die("timed out waiting for job")


def cmd_chat(args):
    if args:
        result = _enqueue_and_wait("chat", " ".join(args))
        print(result if isinstance(result, str) else json.dumps(result, indent=2))
        return 0
    # interactive REPL
    info(f"Terragravity chat — gateway {GATEWAY}. Ctrl-C or 'exit' to quit.")
    session = f"tg-cli-{int(time.time())}"
    try:
        while True:
            try:
                line = input("\033[1;35myou ›\033[0m ").strip()
            except EOFError:
                break
            if not line or line in ("exit", "quit"):
                break
            result = _enqueue_and_wait("chat", line, session_id=session)
            text = result if isinstance(result, str) else json.dumps(result, indent=2)
            print(f"\033[1;32mhermes ›\033[0m {text}\n")
    except KeyboardInterrupt:
        pass
    info("bye")
    return 0


def cmd_agent(args):
    if not args:
        die("usage: tg agent <task...>")
    result = _enqueue_and_wait("agent", " ".join(args))
    print(result if isinstance(result, str) else json.dumps(result, indent=2))
    return 0


def cmd_status(args):
    if not args:
        die("usage: tg status <job_id>")
    status, body = _req("POST", "/status", {"job_id": args[0]})
    print(json.dumps(body, indent=2))
    return 0 if status == 200 else 1


def cmd_logs(args):
    limit = 50
    if "--limit" in args:
        try:
            limit = int(args[args.index("--limit") + 1])
        except Exception:
            pass
    status, body = _req("GET", f"/logs?limit={limit}")
    print(json.dumps(body, indent=2))
    return 0 if status == 200 else 1


COMMANDS = {
    "health": cmd_health,
    "chat": cmd_chat,
    "agent": cmd_agent,
    "status": cmd_status,
    "logs": cmd_logs,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd not in COMMANDS:
        die(f"unknown command: {cmd}\nRun `tg --help` for usage.")
    return COMMANDS[cmd](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
