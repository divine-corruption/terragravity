"""Tests for the Temporal durable-execution integration.

These cover config loading, graceful fallback, and that workflow/activity
definitions are well-formed and importable. A live end-to-end run against
Temporal Cloud is exercised separately (not in unit tests, which must be
hermetic and offline).
"""
from __future__ import annotations

import importlib

import pytest

from app import temporal_config


def test_config_disabled_when_env_missing(monkeypatch):
    for k in ("TEMPORAL_ADDRESS", "TEMPORAL_NAMESPACE", "TEMPORAL_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert temporal_config.load_config() is None


def test_config_enabled_when_env_present(monkeypatch):
    monkeypatch.setenv("TEMPORAL_ADDRESS", "ns.acct.tmprl.cloud:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "ns.acct")
    monkeypatch.setenv("TEMPORAL_API_KEY", "fake-key")
    cfg = temporal_config.load_config()
    assert cfg is not None
    assert cfg.enabled is True
    assert cfg.task_queue == "terragravity-agent"  # default
    assert cfg.address == "ns.acct.tmprl.cloud:7233"


def test_task_queue_override(monkeypatch):
    monkeypatch.setenv("TEMPORAL_ADDRESS", "a:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "ns")
    monkeypatch.setenv("TEMPORAL_API_KEY", "k")
    monkeypatch.setenv("TEMPORAL_TASK_QUEUE", "custom-queue")
    cfg = temporal_config.load_config()
    assert cfg.task_queue == "custom-queue"


def test_partial_config_is_disabled(monkeypatch):
    # address + namespace but no key -> not enabled
    monkeypatch.setenv("TEMPORAL_ADDRESS", "a:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "ns")
    monkeypatch.delenv("TEMPORAL_API_KEY", raising=False)
    assert temporal_config.load_config() is None


def test_workflow_and_activity_importable():
    wf = importlib.import_module("app.temporal_workflows")
    act = importlib.import_module("app.temporal_activities")
    # Workflow class is decorated and has the run + query methods.
    assert hasattr(wf, "AgentJobWorkflow")
    assert hasattr(wf.AgentJobWorkflow, "run")
    assert hasattr(wf.AgentJobWorkflow, "progress")
    # Activity is defined and the input dataclass exists.
    assert hasattr(act, "run_hermes_agent")
    assert hasattr(act, "AgentTaskInput")


def test_workflow_definition_registered():
    """temporalio marks @workflow.defn classes; ensure ours is recognized."""
    from temporalio import workflow

    from app.temporal_workflows import AgentJobWorkflow

    defn = workflow._Definition.from_class(AgentJobWorkflow)
    assert defn is not None
    assert defn.name == "AgentJobWorkflow"


def test_clean_output_strips_banner_and_ansi():
    from app.hermes_bridge import _clean_output

    raw = (
        "\x1b[0;32m\u2713\x1b[0m Detected: linux (ubuntu)\n"
        "\x1b[0;36m\u2192\x1b[0m Checking Node.js (for browser)\n"
        "\u2713 Node.js v22 found\n"
        "DURABLE_HERMES_OK"
    )
    assert _clean_output(raw) == "DURABLE_HERMES_OK"


def test_clean_output_preserves_multiline_answer():
    from app.hermes_bridge import _clean_output

    raw = "\u2713 Detected: linux\nline one\nline two"
    assert _clean_output(raw) == "line one\nline two"
