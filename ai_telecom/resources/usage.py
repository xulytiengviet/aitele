"""Usage — calls, billable minutes and estimated cost, bucketed by day."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..models import Usage
from ._base import BaseResource, unwrap


class UsageResource(BaseResource):
    def get(self, *, from_: Optional[str] = None, until: Optional[str] = None) -> Usage:
        """Defaults to the last 30 days. Days are Asia/Ho_Chi_Minh days.

        ``total.minutes`` / each bucket's ``minutes`` are **billable minutes**:
        each call with talk time contributes ``ceil(duration_sec / 60)`` — the
        same formula used for SIP phone-number quota and the TTS part of
        estimated cost.

        ``cost_usd`` is an estimate and reads 0 when the server has no pricing
        configured — check per-call ``usage.cost_usd is None`` to tell the
        difference between "free" and "unknown".
        """
        params: Dict[str, Any] = {}
        if from_ is not None:
            params["from"] = from_
        if until is not None:
            params["until"] = until
        return Usage.model_validate(unwrap(self._t.request("GET", "/usage", params=params or None)))
