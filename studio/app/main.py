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


@app.post("/chat", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def chat(req: ChatRequest) -> JobResult:
    res = await bridge.chat(req.prompt, session_id=req.session_id)
    return res


@app.post("/execute", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def execute(req: ExecuteRequest) -> JobResult:
    JOBS[req.job_id] = JobResult(job_id=req.job_id, status="running")
    res = await bridge.execute(req.prompt, job_id=req.job_id, session_id=req.session_id)
    JOBS[req.job_id] = res
    return res


@app.post("/status", response_model=JobResult, dependencies=[Depends(verify_signature)])
async def status(req: StatusRequest) -> JobResult:
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
