"""Pydantic models shared across the FastAPI studio server."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    request_uuid: Optional[str] = None


class ExecuteRequest(BaseModel):
    """A longer agent task."""
    prompt: str = Field(..., min_length=1)
    job_id: str
    session_id: Optional[str] = None
    toolsets: Optional[list[str]] = None
    request_uuid: Optional[str] = None


class StatusRequest(BaseModel):
    job_id: Optional[str] = None


class CancelRequest(BaseModel):
    job_id: str


class MemoryRequest(BaseModel):
    action: Literal["get", "set", "list"]
    key: Optional[str] = None
    value: Optional[str] = None


class ShellRequest(BaseModel):
    command: str = Field(..., min_length=1)
    workdir: Optional[str] = None
    timeout: int = 120


class GitRequest(BaseModel):
    op: Literal["status", "add", "commit", "push", "pull", "log"]
    repo: str
    message: Optional[str] = None
    args: Optional[list[str]] = None


class JobResult(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error", "cancelled"]
    response: Optional[str] = None
    error: Optional[str] = None
    exec_ms: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    hermes_reachable: bool
    version: str
    uptime_s: float
