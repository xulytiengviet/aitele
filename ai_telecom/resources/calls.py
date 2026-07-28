"""Calls — the one resource everything else is optional around."""
from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union

from ..models import Call, Page, RecordingLink
from ._base import BaseResource, unwrap


class CallsResource(BaseResource):
    def create(
        self,
        *,
        to: Union[str, Sequence[str]],
        prompt: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent: Optional[dict] = None,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        evaluation: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        knowledge_base_id: Optional[str] = None,
        from_number: Optional[str] = None,
        metadata: Optional[dict] = None,
        config: Optional[dict] = None,
    ) -> Union[Call, List[Call]]:
        """Place a call. A number and a prompt (or agent) are the hard requirements.

            client.calls.create(to="+84901234567", prompt="You are a sales rep…")
            client.calls.create(to="+84901234567", agent_id="agent_x1")
            # Per-call script, keep the agent's voice / KB / config:
            client.calls.create(
                to="+84901234567",
                agent_id="agent_x1",
                prompt="Today only: offer the summer package…",
            )
            # Skip scoring / detach the agent's knowledge base for this call:
            client.calls.create(
                to="+84901234567",
                agent_id="agent_x1",
                evaluation="",
                knowledge_base_id="",
            )

        Resolution order (first non-empty wins per field): top-level kwargs →
        inline ``agent`` dict → ``agent_id`` / default agent.

        Empty string ``""`` on ``evaluation``, ``knowledge_base``, or
        ``knowledge_base_id`` means *explicitly off* (do not fall through to the
        agent). Omit the field (or pass ``None``) to inherit from the agent.

        Passing a list to ``to`` returns a list of Calls, one per number.
        Calls start ``queued``; the dialer places them as the phone number's
        concurrency limit and minute quota allow (each answered call bills
        ``ceil(duration_sec / 60)`` against the line).

        Schedule elsewhere — this API places the call when you call ``create``.
        """
        body: Dict[str, Any] = {"to": to if isinstance(to, str) else list(to)}
        for key, value in (
            ("prompt", prompt),
            ("agent_id", agent_id),
            ("agent", agent),
            ("voice", voice),
            ("speed", speed),
            ("evaluation", evaluation),
            ("knowledge_base", knowledge_base),
            ("knowledge_base_id", knowledge_base_id),
            ("from_number", from_number),
            ("metadata", metadata),
            ("config", config),
        ):
            if value is not None:
                body[key] = value

        raw = unwrap(self._t.request("POST", "/calls", json=body))
        if isinstance(raw, list):
            return [Call.model_validate(item) for item in raw]
        return Call.model_validate(raw)

    def list(
        self,
        *,
        status: Optional[str] = None,
        outcome: Optional[str] = None,
        to: Optional[str] = None,
        agent_id: Optional[str] = None,
        score_min: Optional[int] = None,
        score_max: Optional[int] = None,
        from_: Optional[str] = None,   # ISO date — filters created_at
        until: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Page[Call]:
        params: Dict[str, Any] = {"page": page, "limit": limit}
        for key, value in (
            ("status", status), ("outcome", outcome), ("to", to), ("agent_id", agent_id),
            ("score_min", score_min), ("score_max", score_max),
            ("from", from_), ("until", until),
        ):
            if value is not None:
                params[key] = value
        return Page[Call].model_validate(self._t.request("GET", "/calls", params=params))

    def iter(self, **filters: Any) -> Iterator[Call]:
        """Walk every page, yielding one Call at a time."""
        page = filters.pop("page", 1)
        limit = filters.pop("limit", 50)
        while True:
            result = self.list(page=page, limit=limit, **filters)
            for call in result.data:
                yield call
            if not result.has_next:
                break
            page += 1

    def get(self, call_id: str) -> Call:
        """Full detail: prompt, transcript, score, usage."""
        return Call.model_validate(unwrap(self._t.request("GET", f"/calls/{call_id}")))

    def cancel(self, call_id: str) -> Call:
        """Drop a queued call, or hang up one already in progress."""
        return Call.model_validate(unwrap(self._t.request("DELETE", f"/calls/{call_id}")))

    def recording_url(self, call_id: str) -> RecordingLink:
        """Short-lived signed URL to the recording audio."""
        return RecordingLink.model_validate(unwrap(self._t.request("GET", f"/calls/{call_id}/recording")))

    def wait(self, call_id: str, *, timeout: float = 600.0, poll_interval: float = 5.0) -> Call:
        """Block until the call reaches a terminal state, then return it.

        Convenience for scripts. Prefer the ``call.completed`` webhook in
        production — a call can legitimately run for several minutes, and
        polling holds a process open the whole time.
        """
        deadline = time.monotonic() + timeout
        while True:
            call = self.get(call_id)
            if call.is_done:
                return call
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Call {call_id} still {call.status} after {timeout}s")
            time.sleep(poll_interval)
