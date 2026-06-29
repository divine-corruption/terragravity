"""Temporal activities for Terragravity.

Activities are where side effects live (subprocess, network). They are retried
by Temporal per the workflow's RetryPolicy, so they should be idempotent enough
to re-run safely. Each activity wraps the existing HermesBridge so we reuse the
already-tested transport rather than duplicating it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from temporalio import activity

from .hermes_bridge import HermesBridge
from .models import JobResult


@dataclass
class AgentTaskInput:
    job_id: str
    prompt: str
    session_id: Optional[str] = None


# One bridge instance per worker process.
_bridge = HermesBridge()


@activity.defn
async def run_hermes_agent(inp: AgentTaskInput) -> dict:
    """Run a Hermes agent task. Returns a JobResult as a dict (Temporal-serializable).

    Heartbeats so a long run isn't killed by activity timeout, and so a dead
    worker is detected quickly and the activity is retried on another worker.
    """
    activity.heartbeat("starting")
    result: JobResult = await _bridge.execute(
        inp.prompt, job_id=inp.job_id, session_id=inp.session_id
    )
    activity.heartbeat("done")
    # If Hermes itself errored, raise so Temporal retries per policy.
    if result.status == "error":
        raise RuntimeError(result.error or "hermes agent error")
    return result.model_dump()
