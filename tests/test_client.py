"""SDK tests using httpx.MockTransport — no real server, no network."""
import json

import httpx
import pytest

from ai_telecom import (
    AuthenticationError,
    Client,
    NotFoundError,
    PermissionError_,
    RateLimitError,
    webhooks,
)
from ai_telecom.webhooks import WebhookVerificationError


def make_client(handler, **kwargs):
    """Client wired to a fake transport; handler(request) -> httpx.Response."""
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return Client(api_key="sk_live_test", base_url="https://api.test", http_client=http, **kwargs)


CALL_JSON = {
    "id": "call_abc",
    "object": "call",
    "to": "0901234567",
    "from": "0592014235",
    "status": "queued",
    "agent_id": None,
    "voice": "voice_1",
    "speed": 1.0,
    "metadata": None,
    "duration": None,
    "score": None,
    "outcome": None,
    "summary": None,
    "recording_available": False,
    "dial_status": None,
    "hangup_cause": None,
    "error": None,
    "usage": {"model": None, "input_tokens": None, "output_tokens": None,
              "cost_usd": None, "latency_ms": None},
    "created_at": "2026-07-23T06:00:00.000Z",
    "started_at": None,
    "answered_at": None,
    "ended_at": None,
}


def test_auth_header_and_path():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers.get("Authorization")
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"data": CALL_JSON})

    call = make_client(handler).calls.get("call_abc")
    assert seen["auth"] == "Bearer sk_live_test"
    assert seen["url"] == "https://api.test/api/v1/calls/call_abc"
    assert call.id == "call_abc"
    # `from` is a Python keyword — the model exposes it as `from_`
    assert call.from_ == "0592014235"


def test_create_call_minimal_payload():
    """The headline use case: a number and a prompt, nothing else."""
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        seen["method"] = req.method
        return httpx.Response(201, json={"data": CALL_JSON})

    call = make_client(handler).calls.create(to="+84901234567", prompt="Xin chào")
    assert seen["method"] == "POST"
    # Only what the caller passed is sent — no nulls padding out the request.
    assert seen["body"] == {"to": "+84901234567", "prompt": "Xin chào"}
    assert call.status == "queued"


def test_create_call_batch_returns_list():
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body["to"] == ["0901234567", "0912345678"]
        return httpx.Response(201, json={"data": [CALL_JSON, {**CALL_JSON, "id": "call_def"}]})

    calls = make_client(handler).calls.create(to=["0901234567", "0912345678"], agent_id="agent_x")
    assert isinstance(calls, list)
    assert [c.id for c in calls] == ["call_abc", "call_def"]


def test_list_calls_filters():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["params"] = dict(req.url.params)
        return httpx.Response(200, json={"data": [CALL_JSON], "total": 1, "page": 1, "pages": 1})

    page = make_client(handler).calls.list(status="completed", score_min=60, from_="2026-07-01")
    assert seen["params"]["status"] == "completed"
    assert seen["params"]["score_min"] == "60"
    assert seen["params"]["from"] == "2026-07-01"
    assert len(page) == 1
    assert not page.has_next


def test_iter_walks_every_page():
    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", 1))
        return httpx.Response(200, json={
            "data": [{**CALL_JSON, "id": f"call_{page}"}],
            "total": 3, "page": page, "pages": 3,
        })

    ids = [c.id for c in make_client(handler).calls.iter()]
    assert ids == ["call_1", "call_2", "call_3"]


def test_is_done_flag():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {**CALL_JSON, "status": "completed"}})

    assert make_client(handler).calls.get("call_abc").is_done


def test_cancel_call():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "DELETE"
        return httpx.Response(200, json={"data": {**CALL_JSON, "status": "cancelled"}})

    assert make_client(handler).calls.cancel("call_abc").status == "cancelled"


def test_recording_url():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v1/calls/call_abc/recording"
        return httpx.Response(200, json={"data": {
            "url": "https://r2/x?sig=abc", "expires_at": "2026-07-23T10:05:00Z",
        }})

    assert make_client(handler).calls.recording_url("call_abc").url.startswith("https://r2/")


def test_agent_crud_paths():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path))
        return httpx.Response(200, json={"data": {
            "id": "agent_x", "object": "agent", "name": "A", "prompt": "p",
            "evaluation": None, "voice": "v", "speed": 1.0,
            "knowledge_base_id": None, "is_default": False, "config": {},
        }})

    client = make_client(handler)
    client.agents.create(name="A", prompt="p")
    client.agents.get("agent_x")
    client.agents.update("agent_x", name="B")
    client.agents.delete("agent_x")
    assert seen == [
        ("POST", "/api/v1/agents"),
        ("GET", "/api/v1/agents/agent_x"),
        ("PATCH", "/api/v1/agents/agent_x"),
        ("DELETE", "/api/v1/agents/agent_x"),
    ]


def test_create_call_empty_string_overrides():
    """Empty string means explicit off — must be sent, not dropped as falsy."""
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(201, json={"data": CALL_JSON})

    make_client(handler).calls.create(
        to="+84901234567",
        agent_id="agent_x",
        evaluation="",
        knowledge_base_id="",
    )
    assert seen["body"]["evaluation"] == ""
    assert seen["body"]["knowledge_base_id"] == ""
    assert seen["body"]["agent_id"] == "agent_x"


def test_knowledge_base_and_phone_numbers():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/knowledge-bases") and req.method == "POST":
            return httpx.Response(201, json={"data": {
                "id": "kb_1", "object": "knowledge_base", "name": "Giá",
                "description": None, "document_count": 1, "processing_count": 0,
                "failed_count": 0, "char_count": 1, "effective_char_count": 1,
                "estimated_tokens": 1, "budget_chars": 60000, "over_budget": False,
            }})
        return httpx.Response(200, json={"data": [{
            "id": "1001", "object": "phone_number", "number": "0592014235",
            "trunk": "pstn0592", "status": "active", "concurrent_limit": 1,
            "quota_total": 100, "quota_used": 42, "quota_remaining": 58,
            "calling_hours": {"start": 8, "end": 20, "days": [1, 2, 3, 4, 5, 6]},
        }]})

    client = make_client(handler)
    assert client.knowledge_bases.create(name="Giá", content="x").id == "kb_1"
    numbers = client.phone_numbers.list()
    assert numbers[0].quota_remaining == 58
    assert numbers[0].calling_hours.start == 8


KB_JSON = {
    "id": "kb_1", "object": "knowledge_base", "name": "Bảng giá",
    "description": None,
    "document_count": 1, "processing_count": 0, "failed_count": 0,
    "char_count": 900, "effective_char_count": 700,
    "estimated_tokens": 233, "budget_chars": 60000, "over_budget": False,
    "created_at": "2026-07-23T06:00:00.000Z",
    "updated_at": "2026-07-23T06:00:00.000Z",
    "documents": [{
        "id": "doc_1", "object": "document", "name": "gia.pdf",
        "status": "ready", "enabled": True, "position": 0,
        "source": {"type": "upload", "filename": "gia.pdf", "mime": "application/pdf",
                   "bytes": 1024, "page_count": 3, "ocr_used": True},
        "error": None, "char_count": 900, "effective_char_count": 700, "section_count": 2,
    }],
}

DOC_JSON = {
    "id": "doc_1", "object": "document", "name": "gia.pdf",
    "status": "ready", "enabled": True, "position": 0,
    "source": {"type": "upload", "filename": "gia.pdf", "mime": "application/pdf",
               "bytes": 1024, "page_count": 3, "ocr_used": True},
    "error": None, "char_count": 900, "effective_char_count": 700, "section_count": 2,
    "content": "# Bảng giá\n\nNội dung",
    "sections": [
        {"id": 1, "position": 0, "heading": "Bảng giá", "level": 1,
         "char_count": 400, "enabled": True, "content": "..."},
        {"id": 2, "position": 1, "heading": "Điều khoản", "level": 1,
         "char_count": 500, "enabled": False, "content": "..."},
    ],
}


def test_document_upload_sends_multipart(tmp_path):
    """File upload goes to POST /knowledge-bases/{id}/documents as multipart."""
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["ctype"] = req.headers.get("content-type", "")
        seen["body"] = req.content
        return httpx.Response(202, json={"data": {**DOC_JSON, "status": "processing"}})

    f = tmp_path / "gia.pdf"
    f.write_bytes(b"%PDF-1.4 fake")

    doc = make_client(handler).knowledge_bases.documents.upload("kb_1", f, name="Bảng giá")
    assert seen["path"] == "/api/v1/knowledge-bases/kb_1/documents"
    assert seen["ctype"].startswith("multipart/form-data")
    assert b"%PDF-1.4 fake" in seen["body"]
    assert b"gia.pdf" in seen["body"]
    assert doc.status == "processing"
    assert not doc.is_ready


def test_document_markdown_create_and_crud():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path))
        if req.method == "DELETE":
            return httpx.Response(200, json={"data": {"id": "doc_1", "deleted": True}})
        if req.method == "GET" and req.url.path.endswith("/documents"):
            return httpx.Response(200, json={"data": [DOC_JSON], "total": 1})
        return httpx.Response(200, json={"data": DOC_JSON})

    client = make_client(handler)
    docs = client.knowledge_bases.documents
    assert docs.create("kb_1", name="FAQ", content="# Q\nA").id == "doc_1"
    assert docs.list("kb_1")[0].id == "doc_1"
    assert docs.get("kb_1", "doc_1").sections[0].heading == "Bảng giá"
    docs.update("kb_1", "doc_1", enabled=False)
    docs.delete("kb_1", "doc_1")
    assert seen == [
        ("POST", "/api/v1/knowledge-bases/kb_1/documents"),
        ("GET", "/api/v1/knowledge-bases/kb_1/documents"),
        ("GET", "/api/v1/knowledge-bases/kb_1/documents/doc_1"),
        ("PATCH", "/api/v1/knowledge-bases/kb_1/documents/doc_1"),
        ("DELETE", "/api/v1/knowledge-bases/kb_1/documents/doc_1"),
    ]


def test_knowledge_base_fields_and_documents():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": KB_JSON})

    kb = make_client(handler).knowledge_bases.get("kb_1")
    assert kb.is_ready
    assert kb.processing_count == 0
    assert kb.documents[0].source.ocr_used is True
    assert kb.effective_char_count < kb.char_count


def test_knowledge_base_wait_until_processing_done():
    """wait() returns when processing_count hits 0, even if a doc failed."""
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        processing = 1 if calls["n"] == 1 else 0
        failed = 0 if calls["n"] == 1 else 1
        return httpx.Response(200, json={"data": {
            **KB_JSON,
            "processing_count": processing,
            "failed_count": failed,
            "documents": [{
                **KB_JSON["documents"][0],
                "status": "processing" if processing else "failed",
                "error": None if processing else "PDF được đặt mật khẩu",
            }],
        }})

    kb = make_client(handler).knowledge_bases.wait("kb_1", poll_interval=0)
    assert kb.processing_count == 0
    assert kb.failed_count == 1
    assert kb.is_ready  # ready = nothing still processing
    assert calls["n"] == 2


def test_create_with_upload(tmp_path):
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path))
        if req.method == "POST" and req.url.path.endswith("/knowledge-bases"):
            return httpx.Response(201, json={"data": {**KB_JSON, "processing_count": 0, "document_count": 0}})
        if req.method == "POST" and req.url.path.endswith("/documents"):
            return httpx.Response(202, json={"data": {**DOC_JSON, "status": "processing"}})
        # wait polls GET until processing_count == 0
        return httpx.Response(200, json={"data": KB_JSON})

    f = tmp_path / "gia.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    kb = make_client(handler).knowledge_bases.create_with_upload(f, name="Bảng giá")
    assert kb.id == "kb_1"
    assert kb.is_ready
    assert ("POST", "/api/v1/knowledge-bases") in seen
    assert ("POST", "/api/v1/knowledge-bases/kb_1/documents") in seen


def test_usage_maps_from_keyword():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {
            "from": "2026-06-24T00:00:00.000Z",
            "until": "2026-07-23T00:00:00.000Z",
            "buckets": [{"date": "2026-07-23", "calls": 2, "completed": 1, "minutes": 2,
                         "cost_usd": 0, "input_tokens": 100, "output_tokens": 20}],
            # NOTE: the real server sends `total` WITHOUT a date — an earlier
            # version of this fixture invented one and hid a model bug.
            "total": {"calls": 2, "completed": 1, "minutes": 2,
                      "cost_usd": 0, "input_tokens": 100, "output_tokens": 20},
        }})

    usage = make_client(handler).usage.get()
    assert usage.buckets[0].date == "2026-07-23"
    assert usage.total.calls == 2
    assert usage.from_ is not None


@pytest.mark.parametrize(
    "status,code,exc",
    [
        (401, "invalid_key", AuthenticationError),
        (403, "missing_scope", PermissionError_),
        (404, "not_found", NotFoundError),
    ],
)
def test_error_mapping(status, code, exc):
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"code": code, "message": "boom"}})

    with pytest.raises(exc) as ei:
        make_client(handler).calls.get("call_abc")
    assert ei.value.code == code
    assert ei.value.status_code == status


def test_no_retry_on_logic_errors():
    """A 404 must not be retried — repeating it cannot change the answer."""
    hits = []

    def handler(req: httpx.Request) -> httpx.Response:
        hits.append(1)
        return httpx.Response(404, json={"error": {"code": "not_found", "message": "nope"}})

    with pytest.raises(NotFoundError):
        make_client(handler).calls.get("call_missing")
    assert len(hits) == 1


def test_rate_limit_retries_then_raises():
    hits = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "0"},
                              json={"error": {"code": "rate_limited", "message": "slow down"}})

    with pytest.raises(RateLimitError):
        make_client(handler, max_retries=2).calls.get("call_abc")
    assert hits["n"] == 3   # first attempt + 2 retries


def test_webhook_verify_roundtrip():
    secret = "s3cret"
    body = json.dumps({"event": "call.completed", "data": CALL_JSON})
    sig = webhooks.compute_signature(body, secret)

    event = webhooks.verify(body, sig, secret)
    assert event.event == "call.completed"
    assert event.data.id == "call_abc"

    with pytest.raises(WebhookVerificationError):
        webhooks.verify(body, "sha256=deadbeef", secret)
