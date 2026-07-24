from __future__ import annotations

from typing import Any

from .._http import Transport


class BaseResource:
    def __init__(self, transport: Transport) -> None:
        self._t = transport


def unwrap(raw: Any) -> Any:
    """Peel the ``{"data": …}`` envelope the API wraps single objects in.

    Also tolerates a bare object, so an endpoint that ever stops wrapping does
    not break already-installed SDK versions.
    """
    if isinstance(raw, dict) and "data" in raw:
        return raw["data"]
    return raw
