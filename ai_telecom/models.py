"""Response models mirroring the JSON returned by /api/v1.

Forward-compatible by design: every model sets ``extra="allow"``, so a server
that starts returning a new field never breaks an already-installed SDK.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T", bound=BaseModel)


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class TranscriptTurn(_Base):
    role: str          # "ai" | "user"
    text: str


class GroupScore(_Base):
    name: str
    score: float
    max: float


class CallUsage(_Base):
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    #: ``None`` means the server has no pricing configured — NOT "free".
    cost_usd: Optional[float] = None
    #: Answer → first audio the customer hears.
    latency_ms: Optional[int] = None


class CallError(_Base):
    code: str
    message: Optional[str] = None


class Call(_Base):
    id: str
    object: str = "call"
    to: str
    from_: Optional[str] = None
    status: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    voice: Optional[str] = None
    speed: float = 1.0
    metadata: Optional[dict] = None
    duration: Optional[int] = None
    score: Optional[int] = None
    outcome: Optional[str] = None
    summary: Optional[str] = None
    recording_available: bool = False
    dial_status: Optional[str] = None
    hangup_cause: Optional[str] = None
    error: Optional[CallError] = None
    usage: CallUsage = CallUsage()
    scheduled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    # Only returned by retrieve (GET /calls/{id}); list responses omit these
    # because prompts and transcripts get large.
    prompt: Optional[str] = None
    evaluation: Optional[str] = None
    knowledge_base: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    config: Optional[dict] = None
    group_scores: Optional[List[GroupScore]] = None
    transcript: Optional[List[TranscriptTurn]] = None

    def __init__(self, **data: Any) -> None:
        # `from` is a Python keyword, so the attribute is `from_`. Translate
        # here so callers never have to know about the difference.
        if "from" in data and "from_" not in data:
            data["from_"] = data.pop("from")
        super().__init__(**data)

    @property
    def is_done(self) -> bool:
        """True once the call has reached a terminal state."""
        return self.status in ("completed", "no_answer", "failed", "cancelled")


class Agent(_Base):
    id: str
    object: str = "agent"
    name: str
    prompt: str
    evaluation: Optional[str] = None
    voice: Optional[str] = None
    speed: float = 1.0
    knowledge_base_id: Optional[str] = None
    is_default: bool = False
    config: dict = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class KnowledgeSource(_Base):
    type: str = "manual"          # "manual" | "upload"
    filename: Optional[str] = None
    mime: Optional[str] = None
    bytes: Optional[int] = None
    page_count: Optional[int] = None
    #: True when the document was a scanned PDF and had to be OCR'd.
    ocr_used: bool = False


class KnowledgeSectionModel(_Base):
    id: int
    position: int
    heading: Optional[str] = None
    level: int = 0                # 1 = h1 … 6 = h6; 0 = no heading
    char_count: int = 0
    #: Disabled sections are excluded from the prompt sent to the AI.
    enabled: bool = True
    content: str = ""


class KnowledgeDocument(_Base):
    id: str
    object: str = "document"
    name: str
    status: str = "ready"         # processing | ready | failed
    enabled: bool = True
    position: int = 0
    source: KnowledgeSource = KnowledgeSource()
    error: Optional[str] = None
    char_count: int = 0
    effective_char_count: int = 0
    section_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Retrieve only
    content: Optional[str] = None
    sections: Optional[List[KnowledgeSectionModel]] = None

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"


class KnowledgeBase(_Base):
    """A collection of documents whose enabled content is injected into calls."""
    id: str
    object: str = "knowledge_base"
    name: str
    description: Optional[str] = None
    document_count: int = 0
    processing_count: int = 0
    failed_count: int = 0
    char_count: int = 0
    #: Characters actually sent to the AI (enabled ready docs + enabled sections).
    effective_char_count: int = 0
    estimated_tokens: int = 0
    budget_chars: int = 0
    over_budget: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    #: Present on retrieve (GET one knowledge base).
    documents: Optional[List[KnowledgeDocument]] = None

    @property
    def is_ready(self) -> bool:
        """True when no document is still processing."""
        return self.processing_count == 0


class CallingHours(_Base):
    start: int
    end: int
    #: 0 = Sunday … 6 = Saturday
    days: List[int] = []


class PhoneNumber(_Base):
    id: str
    object: str = "phone_number"
    number: Optional[str] = None
    trunk: Optional[str] = None
    status: str
    concurrent_limit: int = 1
    #: Billable minutes allotted to this SIP line. ``0`` = unlimited.
    quota_total: int = 0
    #: Minutes already consumed — each call bills ``ceil(duration_sec / 60)``.
    quota_used: int = 0
    #: ``None`` means unlimited; otherwise ``max(0, quota_total - quota_used)``.
    quota_remaining: Optional[int] = None
    calling_hours: Optional[CallingHours] = None


class UsageTotals(_Base):
    """Aggregate counters. Shared by each daily bucket and the grand total."""
    calls: int = 0
    completed: int = 0
    #: Billable minutes: ``sum(ceil(duration_sec / 60))`` per call with
    #: ``duration > 0``. Same formula as phone-number SIP ``quota_used`` and
    #: the ElevenLabs portion of estimated ``cost_usd``.
    minutes: float = 0
    cost_usd: float = 0
    input_tokens: int = 0
    output_tokens: int = 0


class UsageBucket(UsageTotals):
    #: YYYY-MM-DD in Asia/Ho_Chi_Minh. Only daily buckets carry a date — the
    #: grand total is a UsageTotals without one.
    date: str


class Usage(_Base):
    from_: Optional[datetime] = None
    until: Optional[datetime] = None
    buckets: List[UsageBucket] = []
    total: Optional[UsageTotals] = None

    def __init__(self, **data: Any) -> None:
        if "from" in data and "from_" not in data:
            data["from_"] = data.pop("from")
        super().__init__(**data)


class RecordingLink(_Base):
    url: str
    expires_at: Optional[datetime] = None


class DeletedResource(_Base):
    id: str
    deleted: bool = True


class Page(_Base, Generic[T]):
    data: List[T] = []
    total: int = 0
    page: int = 1
    pages: int = 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    def __iter__(self):  # type: ignore[override]
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)


class WebhookEvent(_Base):
    """Payload of an incoming webhook: ``{"event": "call.completed", "data": {...}}``."""
    event: str
    data: Call
