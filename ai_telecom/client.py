from __future__ import annotations

from typing import Any, Optional

import httpx

from ._http import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, Transport
from .resources import (
    AgentsResource,
    CallsResource,
    KnowledgeBasesResource,
    PhoneNumbersResource,
    UsageResource,
)

#: Hosted platform. Only override for local development.
DEFAULT_BASE_URL = "https://telecom.mtds.vn"


class Client:
    """Synchronous client for the AI Telecom API.

        from ai_telecom import Client

        client = Client(api_key="sk_live_...")

        call = client.calls.create(
            to="+84901234567",
            prompt="You are a sales rep for MTDS. Greet the customer and ask…",
        )
        print(call.id, call.status)   # call_xxx queued
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._transport = Transport(
            api_key,
            base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )
        self.calls = CallsResource(self._transport)
        self.agents = AgentsResource(self._transport)
        self.knowledge_bases = KnowledgeBasesResource(self._transport)
        self.phone_numbers = PhoneNumbersResource(self._transport)
        self.usage = UsageResource(self._transport)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
