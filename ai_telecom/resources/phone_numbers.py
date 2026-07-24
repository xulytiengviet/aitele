"""Phone numbers — read-only. Numbers are provisioned by an administrator."""
from __future__ import annotations

from typing import List

from ..models import PhoneNumber
from ._base import BaseResource


class PhoneNumbersResource(BaseResource):
    def list(self) -> List[PhoneNumber]:
        """Numbers this account can call from, with quota and calling hours.

        ``quota_*`` are **billable minutes** (each answered call consumes
        ``ceil(duration_sec / 60)``). ``quota_total == 0`` means unlimited.

        Pass one to ``calls.create(from_number=…)``; omit it and the first
        active number is used.
        """
        raw = self._t.request("GET", "/phone-numbers")
        return [PhoneNumber.model_validate(item) for item in (raw.get("data") or [])]
