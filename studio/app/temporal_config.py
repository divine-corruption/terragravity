"""Temporal Cloud connection config — env-driven, secrets never committed.

All values come from the environment (set via .dev.vars locally, or real env in
the Studio). If TEMPORAL_API_KEY is unset, the durable path is considered
disabled and the API falls back to the inline bridge — so the server always
boots, with or without Temporal configured.

Required env (for durable mode):
    TEMPORAL_ADDRESS    e.g. quickstart-terragravity.co1rr.tmprl.cloud:7233
    TEMPORAL_NAMESPACE  e.g. quickstart-terragravity.co1rr
    TEMPORAL_API_KEY    Temporal Cloud API key (JWT)
Optional:
    TEMPORAL_TASK_QUEUE default "terragravity-agent"
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

TASK_QUEUE_DEFAULT = "terragravity-agent"


@dataclass(frozen=True)
class TemporalConfig:
    address: str
    namespace: str
    api_key: str
    task_queue: str = TASK_QUEUE_DEFAULT

    @property
    def enabled(self) -> bool:
        return bool(self.address and self.namespace and self.api_key)


def load_config() -> Optional[TemporalConfig]:
    """Build config from env. Returns None if durable mode isn't configured."""
    address = os.environ.get("TEMPORAL_ADDRESS", "").strip()
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "").strip()
    api_key = os.environ.get("TEMPORAL_API_KEY", "").strip()
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", TASK_QUEUE_DEFAULT).strip()
    if not (address and namespace and api_key):
        return None
    return TemporalConfig(
        address=address, namespace=namespace, api_key=api_key, task_queue=task_queue
    )


async def connect(cfg: TemporalConfig):
    """Connect a Temporal client to Temporal Cloud (TLS + API-key auth).

    Imported lazily so the studio runs without temporalio installed when the
    durable path is disabled.
    """
    from temporalio.client import Client

    return await Client.connect(
        cfg.address,
        namespace=cfg.namespace,
        api_key=cfg.api_key,
        tls=True,
    )
