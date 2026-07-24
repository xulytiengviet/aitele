"""Agents — reusable prompt + evaluation + voice. Entirely optional."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..models import Agent, DeletedResource, Page
from ._base import BaseResource, unwrap


class AgentsResource(BaseResource):
    def create(
        self,
        *,
        name: str,
        prompt: str,
        evaluation: Optional[str] = None,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        knowledge_base_id: Optional[str] = None,
        is_default: Optional[bool] = None,
        config: Optional[dict] = None,
    ) -> Agent:
        """Create an agent you can then reuse via ``calls.create(agent_id=…)``.

        Marking one ``is_default=True`` lets ``calls.create(to=…)`` work with no
        prompt at all. Only one agent per account can be the default.
        """
        body: Dict[str, Any] = {"name": name, "prompt": prompt}
        for key, value in (
            ("evaluation", evaluation), ("voice", voice), ("speed", speed),
            ("knowledge_base_id", knowledge_base_id), ("is_default", is_default),
            ("config", config),
        ):
            if value is not None:
                body[key] = value
        return Agent.model_validate(unwrap(self._t.request("POST", "/agents", json=body)))

    def list(self, *, page: int = 1, limit: int = 50) -> Page[Agent]:
        return Page[Agent].model_validate(
            self._t.request("GET", "/agents", params={"page": page, "limit": limit})
        )

    def get(self, agent_id: str) -> Agent:
        return Agent.model_validate(unwrap(self._t.request("GET", f"/agents/{agent_id}")))

    def update(self, agent_id: str, **fields: Any) -> Agent:
        """Patch any subset of the create fields.

        Editing an agent does NOT change calls that already ran — each call
        snapshots its prompt at creation time.
        """
        return Agent.model_validate(unwrap(self._t.request("PATCH", f"/agents/{agent_id}", json=fields)))

    def delete(self, agent_id: str) -> DeletedResource:
        return DeletedResource.model_validate(unwrap(self._t.request("DELETE", f"/agents/{agent_id}")))
