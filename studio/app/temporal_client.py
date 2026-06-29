"""Thin client helpers the FastAPI layer uses to drive durable workflows.

Kept separate from the worker so the API process can start/query workflows
without importing worker/activity internals. All functions degrade gracefully:
callers check `durable_enabled()` first and fall back to the inline bridge.
"""
from __future__ import annotations

from typing import Optional

from .models import JobResult
from .temporal_config import TemporalConfig, connect, load_config

_WORKFLOW_TYPE = "AgentJobWorkflow"


def durable_enabled() -> Optional[TemporalConfig]:
    """Return config if durable mode is configured, else None."""
    return load_config()


async def start_agent_job(
    cfg: TemporalConfig, job_id: str, prompt: str, session_id: Optional[str] = None
) -> JobResult:
    """Start a durable workflow and return immediately (status=running)."""
    client = await connect(cfg)
    await client.start_workflow(
        _WORKFLOW_TYPE,
        {"job_id": job_id, "prompt": prompt, "session_id": session_id},
        id=f"agent-{job_id}",
        task_queue=cfg.task_queue,
    )
    return JobResult(job_id=job_id, status="running",
                     extra={"durable": True, "workflow_id": f"agent-{job_id}"})


async def get_agent_job(cfg: TemporalConfig, job_id: str) -> JobResult:
    """Query a workflow's state. Returns the final JobResult if completed,
    else a running placeholder reflecting the live `progress` query."""
    from temporalio.service import RPCError

    client = await connect(cfg)
    wf_id = f"agent-{job_id}"
    handle = client.get_workflow_handle(wf_id)
    try:
        desc = await handle.describe()
    except RPCError:
        return JobResult(job_id=job_id, status="error", error="workflow not found")

    # WorkflowExecutionStatus: 1=RUNNING 2=COMPLETED 3=FAILED 4=CANCELED ...
    status_val = int(getattr(desc.status, "value", desc.status))
    if status_val == 2:  # COMPLETED
        result = await handle.result()
        if isinstance(result, dict):
            return JobResult(**result)
        return JobResult(job_id=job_id, status="done", response=str(result))
    if status_val in (3, 4, 5):  # FAILED / CANCELED / TERMINATED
        return JobResult(job_id=job_id, status="error",
                         error=f"workflow ended with status {status_val}")
    # Still running — surface the live stage via the query.
    try:
        stage = await handle.query("progress")
    except Exception:
        stage = "running"
    return JobResult(job_id=job_id, status="running",
                     extra={"durable": True, "workflow_id": wf_id, "stage": stage})
