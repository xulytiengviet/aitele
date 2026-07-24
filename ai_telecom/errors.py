"""Exception tree — maps /api/v1 HTTP statuses onto meaningful Python errors.

The server always returns errors as ``{"error": {"code": ..., "message": ...}}``.
"""
from __future__ import annotations

from typing import Any, Optional


class AITelecomError(Exception):
    """Root error — catch this to catch anything the SDK raises."""


class APIConnectionError(AITelecomError):
    """Could not reach the server (timeout, DNS, refused). Retried automatically."""


class APIStatusError(AITelecomError):
    """The server returned an error status (>= 400)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: Optional[str] = None,
        response_body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.response_body = response_body

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        base = super().__str__()
        return f"[HTTP {self.status_code}]{f' {self.code}' if self.code else ''} {base}"


class AuthenticationError(APIStatusError):
    """401 — API key missing, malformed, or revoked."""


class PermissionError_(APIStatusError):
    """403 — valid key, but it lacks the scope this endpoint needs."""


class NotFoundError(APIStatusError):
    """404 — no such resource (or it belongs to another account)."""


class ValidationError_(APIStatusError):
    """400/422 — invalid request payload."""


class RateLimitError(APIStatusError):
    """429 — rate limit or quota exceeded. ``retry_after`` is in seconds."""

    def __init__(self, *args: Any, retry_after: Optional[float] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class ServerError(APIStatusError):
    """5xx — server-side failure. Retried automatically."""


def error_from_response(status_code: int, code: Optional[str], message: str, body: Any) -> APIStatusError:
    """Pick the right exception class for a status code."""
    kwargs = dict(status_code=status_code, code=code, response_body=body)
    if status_code == 401:
        return AuthenticationError(message, **kwargs)
    if status_code == 403:
        return PermissionError_(message, **kwargs)
    if status_code == 404:
        return NotFoundError(message, **kwargs)
    if status_code in (400, 422):
        return ValidationError_(message, **kwargs)
    if status_code == 429:
        return RateLimitError(message, **kwargs)
    if status_code >= 500:
        return ServerError(message, **kwargs)
    return APIStatusError(message, **kwargs)
