"""Bridge between the FastAPI server and the Hermes agent.

Default strategy: invoke the Hermes CLI as a subprocess (`hermes chat -q`)
with a job-scoped session id. This keeps the server decoupled from Hermes
internals and survives Hermes upgrades. A long-lived in-process bridge can
be swapped in later behind the same interface.

All methods are async and never raise to the caller — they return a JobResult
with status="error" on failure, so the API layer always has something to log.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from typing import Optional

from .models import JobResult

HERMES_BIN = os.environ.get("HERMES_BIN", "hermes")
HERMES_TIMEOUT_S = int(os.environ.get("HERMES_TIMEOUT_S", "600"))

import re as _re

# Strip ANSI escape sequences and known setup/postinstall banner lines that some
# Hermes builds print to stdout before the actual answer.
_ANSI = _re.compile(r"\x1b\[[0-9;]*m")
_BANNER_PREFIXES = ("✓ ", "→ ", "✗ ", "Detected:", "Checking ", "Node.js")


def _clean_output(raw: str) -> str:
    text = _ANSI.sub("", raw)
    lines = text.splitlines()
    # Drop leading banner/diagnostic lines; keep everything from the first
    # "real" content line onward (preserves multi-line answers).
    start = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            start = i + 1
            continue
        if s.startswith(_BANNER_PREFIXES):
            start = i + 1
            continue
        break
    return "\n".join(lines[start:]).strip()


def hermes_available() -> bool:
    """True if the hermes binary is on PATH (used by /health)."""
    return shutil.which(HERMES_BIN) is not None


async def _run(cmd: list[str], timeout: int, cwd: Optional[str] = None) -> tuple[int, str, str]:
    """Run a subprocess, return (rc, stdout, stderr). Never raises on timeout."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", f"timed out after {timeout}s"
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


class HermesBridge:
    """Interface to a Hermes instance via the CLI."""

    def __init__(self, bin_path: str = HERMES_BIN):
        self.bin = bin_path
        self._cli_supported: Optional[bool] = None

    def _supports_cli(self) -> bool:
        """Return True if `hermes chat` advertises a `--cli` flag.

        Cached after first probe. Newer builds default to the classic REPL and
        dropped `--cli`; older/TUI-default builds need it. Detecting avoids
        hardcoding a flag that crashes one build or the other.
        """
        if self._cli_supported is None:
            try:
                import subprocess
                out = subprocess.run(
                    [self.bin, "chat", "--help"],
                    capture_output=True, text=True, timeout=15,
                )
                self._cli_supported = "--cli" in (out.stdout + out.stderr)
            except Exception:
                self._cli_supported = False
        return self._cli_supported

    async def chat(self, prompt: str, session_id: Optional[str] = None,
                   job_id: str = "chat") -> JobResult:
        """One-shot chat. Bounded by HERMES_TIMEOUT_S.

        We invoke the classic REPL oneshot (`hermes chat -q ... --quiet`). The
        classic REPL is the default; the TUI is opt-in via `--tui`, so we simply
        never request the TUI. Older builds exposed an explicit `--cli` flag —
        if (and only if) this binary advertises it, we pass it for safety on
        configs whose default interface is the TUI. Detection is cached.
        """
        t0 = time.time()
        cmd = [self.bin, "chat", "-q", prompt, "-Q"]
        if self._supports_cli():
            cmd.append("--cli")
        if session_id:
            cmd += ["--source", f"gw:{session_id}"]
        rc, out, err = await _run(cmd, HERMES_TIMEOUT_S)
        exec_ms = int((time.time() - t0) * 1000)
        if rc != 0:
            return JobResult(job_id=job_id, status="error",
                             error=err.strip() or f"hermes exited {rc}", exec_ms=exec_ms)
        return JobResult(job_id=job_id, status="done",
                         response=_clean_output(out), exec_ms=exec_ms)

    async def execute(self, prompt: str, job_id: str,
                      session_id: Optional[str] = None) -> JobResult:
        """Longer agent task. Same transport for now; separate hook for streaming later."""
        return await self.chat(prompt, session_id=session_id, job_id=job_id)

    async def shell(self, command: str, workdir: Optional[str] = None,
                    timeout: int = 120) -> JobResult:
        """Allowlisted shell exec. The route layer enforces the allowlist;
        this just runs it. Returns combined output."""
        t0 = time.time()
        rc, out, err = await _run(["bash", "-lc", command], timeout, cwd=workdir)
        exec_ms = int((time.time() - t0) * 1000)
        status = "done" if rc == 0 else "error"
        return JobResult(
            job_id="shell", status=status,
            response=out.strip(), error=(err.strip() or None) if rc else None,
            exec_ms=exec_ms, extra={"rc": rc},
        )

    async def git(self, op: str, repo: str, message: Optional[str] = None,
                  args: Optional[list[str]] = None) -> JobResult:
        t0 = time.time()
        gitcmd = ["git", "-C", repo, op]
        if op == "commit" and message:
            gitcmd += ["-m", message]
        if args:
            gitcmd += args
        rc, out, err = await _run(gitcmd, 120)
        exec_ms = int((time.time() - t0) * 1000)
        status = "done" if rc == 0 else "error"
        return JobResult(job_id="git", status=status, response=out.strip(),
                         error=(err.strip() or None) if rc else None,
                         exec_ms=exec_ms, extra={"rc": rc, "op": op})
