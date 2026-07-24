"""ai-telecom — Python SDK for the AI Telecom voice API.

    pip install ai-telecom

    from ai_telecom import Client

    client = Client(api_key="sk_live_...")
    call = client.calls.create(to="+84901234567", prompt="You are a sales rep…")
"""
from ._version import __version__
from .client import Client, DEFAULT_BASE_URL
from .errors import (
    AITelecomError,
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    NotFoundError,
    PermissionError_,
    RateLimitError,
    ServerError,
    ValidationError_,
)
from .models import (
    Agent,
    Call,
    CallError,
    CallUsage,
    CallingHours,
    DeletedResource,
    GroupScore,
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeSectionModel,
    KnowledgeSource,
    Page,
    PhoneNumber,
    RecordingLink,
    TranscriptTurn,
    Usage,
    UsageBucket,
    UsageTotals,
    WebhookEvent,
)
from . import webhooks

__all__ = [
    "__version__",
    "Client",
    "DEFAULT_BASE_URL",
    "webhooks",
    # errors
    "AITelecomError",
    "APIConnectionError",
    "APIStatusError",
    "AuthenticationError",
    "PermissionError_",
    "NotFoundError",
    "ValidationError_",
    "RateLimitError",
    "ServerError",
    # models
    "Call",
    "CallError",
    "CallUsage",
    "TranscriptTurn",
    "GroupScore",
    "Agent",
    "KnowledgeBase",
    "KnowledgeDocument",
    "KnowledgeSource",
    "KnowledgeSectionModel",
    "PhoneNumber",
    "CallingHours",
    "Usage",
    "UsageBucket",
    "UsageTotals",
    "RecordingLink",
    "DeletedResource",
    "Page",
    "WebhookEvent",
]
