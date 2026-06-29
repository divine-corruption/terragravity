"""Tests for the Terragravity Studio API.

Run: cd studio && PYTHONPATH=. pytest -q
"""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

# Force a known HMAC secret for signed-path tests BEFORE importing the app.
os.environ.pop("GATEWAY_DEV_INSECURE", None)
os.environ["GATEWAY_HMAC_SECRET"] = "test-secret-123"

from app.auth import sign  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
SECRET = b"test-secret-123"


def _signed_headers(method: str, path: str, body: bytes):
    ts = str(int(time.time()))
    return {
        "X-Timestamp": ts,
        "X-Signature": sign(ts, method, path, body, SECRET),
        "Content-Type": "application/json",
    }


def test_health_is_public_and_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert body["version"] == "0.1.0"
    assert "uptime_s" in body


def test_signed_route_rejects_unsigned():
    r = client.post("/chat", json={"prompt": "hi"})
    assert r.status_code == 401


def test_signed_route_rejects_bad_signature():
    body = b'{"prompt":"hi"}'
    headers = _signed_headers("POST", "/chat", body)
    headers["X-Signature"] = "deadbeef"
    r = client.post("/chat", content=body, headers=headers)
    assert r.status_code == 401


def test_signed_route_rejects_stale_timestamp():
    body = b'{"prompt":"hi"}'
    old = str(int(time.time()) - 99999)
    headers = {
        "X-Timestamp": old,
        "X-Signature": sign(old, "POST", "/chat", body, SECRET),
        "Content-Type": "application/json",
    }
    r = client.post("/chat", content=body, headers=headers)
    assert r.status_code == 401


def test_shell_runs_with_valid_signature(monkeypatch):
    # Patch the bridge so we don't depend on a real shell behavior beyond echo.
    body = b'{"command":"echo TERRAGRAVITY_OK"}'
    headers = _signed_headers("POST", "/shell", body)
    r = client.post("/shell", content=body, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "done"
    assert "TERRAGRAVITY_OK" in (data["response"] or "")


def test_git_status_signed(tmp_path):
    # init a throwaway repo so `git status` succeeds
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    body = ('{"op":"status","repo":"%s"}' % str(tmp_path)).encode()
    headers = _signed_headers("POST", "/git", body)
    r = client.post("/git", content=body, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"
