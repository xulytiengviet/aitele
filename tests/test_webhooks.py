import json

import pytest

from ai_telecom import webhooks
from ai_telecom.webhooks import WebhookVerificationError

CALL = {
    "id": "call_abc",
    "object": "call",
    "to": "0901234567",
    "status": "completed",
    "score": 72,
    "outcome": "potential",
    "recording_available": True,
}


def _body() -> str:
    return json.dumps({"event": "call.completed", "data": CALL})


def test_verify_ok():
    secret = "whsec_123"
    body = _body()
    ev = webhooks.verify(body, webhooks.compute_signature(body, secret), secret)
    assert ev.event == "call.completed"
    assert ev.data.id == "call_abc"
    assert ev.data.score == 72
    assert ev.data.outcome == "potential"


def test_verify_bad_signature():
    with pytest.raises(WebhookVerificationError):
        webhooks.verify(_body(), "sha256=deadbeef", "whsec_123")


def test_verify_bytes_payload():
    """The raw body arrives as bytes in most web frameworks — must work as-is."""
    secret = "s"
    body = _body().encode("utf-8")
    ev = webhooks.verify(body, webhooks.compute_signature(body, secret), secret)
    assert ev.data.to == "0901234567"


def test_signature_is_secret_dependent():
    body = _body()
    assert webhooks.compute_signature(body, "a") != webhooks.compute_signature(body, "b")
