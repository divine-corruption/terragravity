"""Terragravity Studio API — FastAPI server running beside Hermes.

Exposes the private upstream that the Cloudflare queue-consumer Worker calls
over a Cloudflare Tunnel. Every mutating route is guarded by HMAC signature
verification (see auth.verify_signature).

Run locally:
    GATEWAY_DEV_INSECURE=1 uvicorn app.main:app --reload --port 8088
"""
from __future__ import annotations

import time

from fastapi import Depends, FastAPI

from .auth import verify_signature
from .hermes_bridge import HermesBridge, hermes_available
from .temporal_client import durable_enabled, get_agent_job, start_agent_job
from .models import (
    CancelRequest,
    ChatRequest,
    ExecuteRequest,
    GitRequest,
    HealthResponse,
    JobResult,
    MemoryRequest,
    ShellRequest,
    StatusRequest,
)

VERSION = "0.1.0"
_START = time.time()

app = FastAPI(title="Terragravity Studio API", version=VERSION)
bridge = HermesBridge()

# In-process job registry (Phase 1 — replaced by D1-backed status in integration).
JOBS: dict[str, JobResult] = {}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    reachable = hermes_available()
    return HealthResponse(
        status="ok" if reachable else "degraded",
        hermes_reachable=reachable,
        version=VERSION,
        uptime_s=round(time.time() - _START, 2),
    )


# The edge Worker probes upstream health with a POST (its callStudio helper
# always POSTs). Mirror the GET handler so the tunnel health check succeeds.
# Intentionally unsigned — health carries no sensitive data or side effects.
@app.post("/health", response_model=HealthResponse)
async def health_post() -> HealthResponse:
    return await health()


@app.post("/chat", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def chat(req: ChatRequest) -> JobResult:
    res = await bridge.chat(req.prompt, session_id=req.session_id)
    return res


@app.post("/execute", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def execute(req: ExecuteRequest) -> JobResult:
    """Long agent task. Durable via Temporal when configured, else inline.

    Durable mode returns immediately with status=running and a workflow_id;
    the client polls /status. Inline mode (no Temporal) runs to completion.
    """
    cfg = durable_enabled()
    if cfg is not None:
        return await start_agent_job(
            cfg, job_id=req.job_id, prompt=req.prompt, session_id=req.session_id
        )
    # Fallback: inline execution with in-process registry.
    JOBS[req.job_id] = JobResult(job_id=req.job_id, status="running")
    res = await bridge.execute(req.prompt, job_id=req.job_id, session_id=req.session_id)
    JOBS[req.job_id] = res
    return res


@app.post("/status", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def status(req: StatusRequest) -> JobResult:
    cfg = durable_enabled()
    if cfg is not None and req.job_id:
        return await get_agent_job(cfg, req.job_id)
    if req.job_id and req.job_id in JOBS:
        return JOBS[req.job_id]
    return JobResult(job_id=req.job_id or "unknown", status="error", error="job not found")


@app.post("/cancel", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def cancel(req: CancelRequest) -> JobResult:
    job = JOBS.get(req.job_id)
    if job and job.status == "running":
        job.status = "cancelled"
        JOBS[req.job_id] = job
        return job
    return JobResult(job_id=req.job_id, status="error", error="job not running")


@app.post("/memory", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def memory(req: MemoryRequest) -> JobResult:
    # Phase 1 stub: memory ops are routed through Hermes in integration.
    return JobResult(job_id="memory", status="done",
                     response=f"memory.{req.action} acknowledged", extra={"key": req.key})


@app.post("/shell", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def shell(req: ShellRequest) -> JobResult:
    return await bridge.shell(req.command, workdir=req.workdir, timeout=req.timeout)


@app.post("/git", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def git(req: GitRequest) -> JobResult:
    return await bridge.git(req.op, req.repo, message=req.message, args=req.args)
