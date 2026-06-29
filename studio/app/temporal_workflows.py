"""Temporal workflow definitions for Terragravity.

Workflow code MUST be deterministic: no subprocess, no direct network, no
wall-clock reads outside the Temporal APIs. All side effects are delegated to
activities (see temporal_activities.py). This is what makes a run durable — the
workflow can be replayed from history after a crash and reach the same state.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .temporal_activities import AgentTaskInput, run_hermes_agent


@workflow.defn
class AgentJobWorkflow:
    """Durable wrapper around a single Hermes agent task.

    Exposes a `progress` query so the API /status route can read live state
    without touching any in-process dict — the source of truth is Temporal.
    """

    def __init__(self) -> None:
        self._stage: str = "queued"

    @workflow.query
    def progress(self) -> str:
        return self._stage

    @workflow.run
    async def run(self, inp: AgentTaskInput) -> dict:
        self._stage = "running"
        result = await workflow.execute_activity(
            run_hermes_agent,
            inp,
            start_to_close_timeout=timedelta(minutes=20),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=4,
            ),
        )
        self._stage = "done"
        return result
