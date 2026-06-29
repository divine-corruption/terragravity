"""HMAC request-signing verification for the studio API.

The Cloudflare Worker signs every upstream request:

    signature = HMAC_SHA256(secret, f"{timestamp}\\n{method}\\n{path}\\n{body}")

sent as headers:
    X-Timestamp: <unix seconds>
    X-Signature: <hex>

We reject requests with a skewed timestamp (> MAX_SKEW_S) to bound replay,
and constant-time compare the signature. A shared secret lives in the Studio
env (GATEWAY_HMAC_SECRET) and in `wrangler secret` on the edge.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import Header, HTTPException, Request

MAX_SKEW_S = int(os.environ.get("GATEWAY_MAX_SKEW_S", "300"))


def _secret() -> bytes:
    s = os.environ.get("GATEWAY_HMAC_SECRET", "")
    if not s:
        # Fail closed in production; allow a dev bypass only when explicitly set.
        if os.environ.get("GATEWAY_DEV_INSECURE") == "1":
            return b"dev-insecure-secret"
        raise HTTPException(status_code=500, detail="GATEWAY_HMAC_SECRET not configured")
    return s.encode()


def sign(timestamp: str, method: str, path: str, body: bytes, secret: bytes) -> str:
    msg = b"\n".join([timestamp.encode(), method.encode(), path.encode(), body])
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


async def verify_signature(
    request: Request,
    x_timestamp: str = Header(default=""),
    x_signature: str = Header(default=""),
) -> None:
    """FastAPI dependency: raises 401 on any auth failure."""
    if os.environ.get("GATEWAY_DEV_INSECURE") == "1":
        return  # explicit local-dev bypass

    if not x_timestamp or not x_signature:
        raise HTTPException(status_code=401, detail="missing signature headers")
    try:
        ts = int(x_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="bad timestamp")
    if abs(time.time() - ts) > MAX_SKEW_S:
        raise HTTPException(status_code=401, detail="timestamp skew too large")

    body = await request.body()
    expected = sign(x_timestamp, request.method, request.url.path, body, _secret())
    if not hmac.compare_digest(expected, x_signature):
        raise HTTPException(status_code=401, detail="signature mismatch")
