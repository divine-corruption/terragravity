"""Terragravity Temporal worker.

Runs beside Hermes in the Studio, polling the task queue and executing
AgentJobWorkflow + its activities. If a worker dies mid-task, Temporal Cloud
re-dispatches the workflow to another worker and it resumes from history.

Run:
    set -a; source .dev.vars; set +a   # load TEMPORAL_* env
    PYTHONPATH=. python -m app.temporal_worker
"""
from __future__ import annotations

import asyncio
import logging

from .temporal_activities import run_hermes_agent
from .temporal_config import connect, load_config
from .temporal_workflows import AgentJobWorkflow

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("terragravity.worker")


async def main() -> None:
    cfg = load_config()
    if cfg is None:
        raise SystemExit(
            "Temporal not configured: set TEMPORAL_ADDRESS / TEMPORAL_NAMESPACE / "
            "TEMPORAL_API_KEY (e.g. via .dev.vars) before starting the worker."
        )

    from temporalio.worker import Worker

    client = await connect(cfg)
    log.info("connected to %s ns=%s; polling task_queue=%s",
             cfg.address, cfg.namespace, cfg.task_queue)

    worker = Worker(
        client,
        task_queue=cfg.task_queue,
        workflows=[AgentJobWorkflow],
        activities=[run_hermes_agent],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
