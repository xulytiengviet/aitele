"""Verify incoming webhooks.

The server signs the raw body with HMAC-SHA256 using your ``webhook_secret``
and sends it as ``X-Signature: sha256=<hex>``. Call :func:`verify` on every
incoming request before trusting the payload.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Union

from .errors import AITelecomError
from .models import WebhookEvent


class WebhookVerificationError(AITelecomError):
    """Signature mismatch — do NOT trust this payload."""


def _to_bytes(v: Union[str, bytes]) -> bytes:
    return v.encode("utf-8") if isinstance(v, str) else v


def compute_signature(payload: Union[str, bytes], secret: str) -> str:
    """Compute the signature the same way the server does (useful in tests)."""
    mac = hmac.new(_to_bytes(secret), _to_bytes(payload), hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def verify(
    payload: Union[str, bytes], signature: str, secret: str
) -> WebhookEvent:
    """Verify and parse. Raises WebhookVerificationError on a bad signature.

    ``payload`` must be the RAW body (bytes/str, NOT json.loads-ed) — it has to
    match byte-for-byte what the server signed.
    """
    expected = compute_signature(payload, secret)
    provided = (signature or "").strip()
    # constant-time compare — defeats timing attacks
    if not hmac.compare_digest(expected, provided):
        raise WebhookVerificationError("Invalid webhook signature.")

    import json

    data = json.loads(payload)
    return WebhookEvent.model_validate(data)
