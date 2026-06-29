"""Cross-language HMAC contract test.

Locks the Python signer to the SAME known vector the Worker's TypeScript
test asserts (worker/test/auth.test.ts KNOWN_VECTOR). If either side changes
the signing format, one of these tests fails loudly.
"""
from app.auth import sign

KNOWN_VECTOR = "a7edc015199788fd06256f3d09e686e658a81410289f31873d7947ee755c9c24"


def test_python_matches_worker_known_vector():
    sig = sign(
        "1700000000",
        "POST",
        "/chat",
        b'{"prompt":"hi"}',
        b"shared",
    )
    assert sig == KNOWN_VECTOR
