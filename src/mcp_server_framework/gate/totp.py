"""TOTP — RFC 6238. Pure stdlib, no pyotp dependency."""

from __future__ import annotations
import base64
import hashlib
import hmac
import os
import struct
import time


def _hotp(secret_bytes: bytes, counter: int) -> int:
    msg = struct.pack(">Q", counter)
    h = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    return (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % 10**6


def verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
    """Verify 6-digit TOTP. window=1 allows ±30s clock drift."""
    try:
        secret_bytes = base64.b32decode(secret_b32.upper().strip())
        code_int = int(code.strip())
    except Exception:
        return False
    t = int(time.time()) // 30
    for delta in range(-window, window + 1):
        if _hotp(secret_bytes, t + delta) == code_int:
            return True
    return False


def generate_secret() -> str:
    """Generate a new random Base32 secret (for setup/tests)."""
    return base64.b32encode(os.urandom(20)).decode()
