<p align="center">
  <img src="https://telecom.mtds.vn/logo.png" alt="MTDS — AI Telecom" width="220" />
</p>

<h1 align="center">ai-telecom</h1>

<p align="center">
  Python SDK for <a href="https://telecom.mtds.vn/"><strong>AI Telecom</strong></a> —
  place AI phone calls with a number and a prompt.
</p>

<p align="center">
  <a href="https://telecom.mtds.vn/">Platform</a> ·
  <a href="https://telecom.mtds.vn/api-docs.html">API reference</a> ·
  <a href="https://telecom.mtds.vn/openapi.yaml">OpenAPI</a>
</p>

---

```bash
pip install ai-telecom
```

```python
from ai_telecom import Client

client = Client(api_key="sk_live_...")

call = client.calls.create(
    to="+84901234567",
    prompt="""
    Bạn là nhân viên tư vấn của MTDS.
    Chào khách, hỏi xem anh chị có quan tâm gói internet không.
    """,
)

print(call.id, call.status)   # call_Ku3n8pQ7... queued
```

That is the whole getting-started. No campaign, no contact list, no workflow to
build first — a phone number and a prompt is the complete API surface you need.

`base_url` defaults to `https://telecom.mtds.vn`; pass it only when developing
against a local deployment.

---

## Calls

```python
# Prompt inline
client.calls.create(to="+84901234567", prompt="...")

# Pick a voice (Vietnamese default on the platform is Giang)
client.calls.create(to="+84901234567", prompt="...", voice="s6W2NupNY6TykGJoDtWy")

# Reuse a saved agent
client.calls.create(to="+84901234567", agent_id="agent_9fQz...")

# Per-call script; keep the agent's voice / KB / config
client.calls.create(
    to="+84901234567",
    agent_id="agent_9fQz...",
    prompt="Hôm nay chỉ nói về gói mùa hè…",
)

# Skip scoring / detach the agent's knowledge base for this call
client.calls.create(
    to="+84901234567",
    agent_id="agent_9fQz...",
    evaluation="",
    knowledge_base_id="",
)

# Many numbers at once → returns a list
client.calls.create(to=["+84901234567", "+84912345678"], agent_id="agent_9fQz...")

# Schedule for later, and attach your own IDs
client.calls.create(
    to="+84901234567",
    prompt="...",
    scheduled_at="2026-08-01T02:00:00Z",
    metadata={"crm_id": "C-42"},
)
```

The prompt is resolved in this order, first match wins:
**inline `prompt` → inline `agent` → `agent_id` → your default agent.**

Empty string `""` on `evaluation`, `knowledge_base`, or `knowledge_base_id`
means *explicitly off* (do not inherit from the agent). Omit the field to inherit.

Whatever is resolved gets snapshotted onto the call, so editing an agent later
never rewrites a call that already ran.

### Reading results

```python
call = client.calls.get("call_Ku3n8pQ7...")

call.status        # completed | no_answer | failed | cancelled | queued | dialing | ringing | in_progress
call.duration      # seconds of actual conversation (ringing excluded)
call.transcript    # [TranscriptTurn(role="ai", text="..."), ...]
call.score         # 0–100, only when you passed `evaluation`
call.outcome       # potential | follow_up | not_interested
call.summary
call.usage.cost_usd      # None means "no pricing configured", NOT free
call.usage.latency_ms    # answer → first audio the customer hears

# Recording (signed URL, expires in 10 minutes)
client.calls.recording_url(call.id).url
```

### Listing and filtering

```python
client.calls.list(status="completed", score_min=70)
client.calls.list(status="dialing,ringing,in_progress")   # anything live
client.calls.list(to="0901234567")
client.calls.list(from_="2026-07-01", until="2026-07-31")

# Walk every page without managing offsets yourself
for call in client.calls.iter(outcome="potential"):
    print(call.to, call.score)
```

### Cancelling

```python
client.calls.cancel("call_Ku3n8pQ7...")   # drops from queue, or hangs up mid-call
```

### Waiting for a result

```python
call = client.calls.wait("call_Ku3n8pQ7...", timeout=600)
print(call.score, call.summary)
```

`wait()` polls, which is fine for scripts. In production prefer the
`call.completed` webhook — a call can legitimately run for minutes.

---

## Scoring a call

Pass `evaluation` and the platform scores the conversation after it ends:

```python
client.calls.create(
    to="+84901234567",
    prompt="Bạn là nhân viên tư vấn...",
    evaluation="""
    Chấm 0–100:
    - Khách có quan tâm sản phẩm không
    - Khách có hỏi về giá không
    - Khách có đồng ý hẹn gặp không
    """,
)
```

Omit it and the call still runs — it simply returns no `score`, `outcome` or
`summary`, and skips the scoring model entirely.

---

## Agents (optional)

An agent is a saved prompt + evaluation + voice. Use one when you want to reuse
the same script across many calls.

```python
agent = client.agents.create(
    name="Fibre internet outreach",
    prompt="Bạn là nhân viên tư vấn của MTDS...",
    evaluation="Chấm 0–100 theo mức độ quan tâm.",
    is_default=True,     # now calls.create(to=...) works with no prompt at all
)

client.calls.create(to="+84901234567", agent_id=agent.id)

client.agents.list()
client.agents.update(agent.id, prompt="...")
client.agents.delete(agent.id)
```

---

## Knowledge bases (optional)

A knowledge base is a **collection of documents**. Reference material the AI
consults when the customer asks — a price list, an FAQ, product specs.

```python
# Empty collection, then Markdown document
kb = client.knowledge_bases.create(name="Bảng giá 2026")
doc = client.knowledge_bases.documents.create(
    kb.id,
    name="Gói cước",
    content="Gói Cơ bản: hai trăm nghìn đồng một tháng...",
)

# …or upload a file into the collection (PDF, DOCX, PPTX, XLSX, HTML, TXT, MD)
doc = client.knowledge_bases.documents.upload(kb.id, "bang-gia.pdf")
kb = client.knowledge_bases.wait(kb.id)   # until processing_count == 0

# Shortcut: create + upload + wait
kb = client.knowledge_bases.create_with_upload("bang-gia.pdf", name="Bảng giá 2026")

if kb.failed_count:
    print("Một số tài liệu lỗi — kiểm tra documents")
elif kb.is_ready:
    for d in kb.documents or []:
        print(d.name, d.status, d.effective_char_count)
    full = client.knowledge_bases.documents.get(kb.id, kb.documents[0].id)
    print(full.content)
    for s in full.sections or []:
        print(s.level, s.heading, s.char_count, s.enabled)
```

File upload returns immediately with document `status="processing"`. Poll the
**knowledge base** with `wait()` (or `get()`) until `processing_count == 0`
before using it — otherwise `calls.create` returns `knowledge_base_processing`
or `knowledge_base_unavailable`.

`wait()` also returns when some documents `failed` (password-protected PDF,
unsupported format) — check `failed_count` / each document's `error`.

### Attaching it

```python
# To an agent…
client.agents.create(name="Sales", prompt="...", knowledge_base_id=kb.id)

# …or straight into one call
client.calls.create(to="+84901234567", prompt="...", knowledge_base_id=kb.id)
client.calls.create(to="+84901234567", prompt="...", knowledge_base="Giá: ...")

# Detach the agent's KB for one call
client.calls.create(to="+84901234567", agent_id=agent.id, knowledge_base_id="")
```

### Size is a real cost

There is no retrieval step: the **entire** enabled content of the knowledge
base goes into the system prompt of **every** call that uses it.
`estimated_tokens` is therefore per-call cost, not a one-off. Disable documents
or sections you don't need in the dashboard — `effective_char_count` shows what
is actually sent.

> Write numbers as words ("hai trăm nghìn", not "200000") — the text is spoken
> aloud, and digits are read unreliably.

## Phone numbers

Read-only; numbers are provisioned by an administrator.

```python
for number in client.phone_numbers.list():
    print(number.number, number.status, number.quota_remaining)

client.calls.create(to="+84901234567", prompt="...", from_number="0592014235")
```

Each number carries its own **concurrency limit**, **minute quota** and
**calling hours**. Minute quota uses the same billable-minute rule as Usage:
each answered call consumes `ceil(duration_sec / 60)`. A call created when the
line is out of minutes is rejected (`429 quota_exceeded`).

---

## Usage

```python
usage = client.usage.get()                      # last 30 days
usage = client.usage.get(from_="2026-07-01")

print(usage.total.calls, usage.total.minutes)
for day in usage.buckets:
    print(day.date, day.calls, day.cost_usd)
```

`minutes` are **billable minutes**: each call with talk time contributes
`ceil(duration_sec / 60)` — matching phone-number SIP quota and the TTS
portion of estimated `cost_usd`. Example: three 30-second calls → `3` minutes,
not `1.5`.

---

## Webhooks

Set a webhook URL on your API key in the dashboard. Every finished call is
POSTed to it, signed with HMAC-SHA256 in the `X-Signature` header.

```python
from ai_telecom import webhooks
from ai_telecom.webhooks import WebhookVerificationError

@app.post("/hooks/ai-telecom")
def handle(request):
    try:
        event = webhooks.verify(
            request.body,                      # RAW bytes — do NOT json.loads first
            request.headers["X-Signature"],
            secret=WEBHOOK_SECRET,
        )
    except WebhookVerificationError:
        return 400

    call = event.data                          # a full Call object
    print(call.id, call.score, call.metadata)
    return 200
```

Verification is constant-time. Always verify before trusting a payload.

---

## Errors

```python
from ai_telecom import (
    AITelecomError,        # base class — catches everything below
    AuthenticationError,   # 401
    PermissionError_,      # 403 — key lacks the scope
    NotFoundError,         # 404
    ValidationError_,      # 400 / 422
    RateLimitError,        # 429 — has .retry_after
    ServerError,           # 5xx
    APIConnectionError,    # network failure
)

try:
    client.calls.create(to="not-a-number", prompt="...")
except ValidationError_ as e:
    print(e.code, e)       # invalid_phone  `not-a-number` is not a valid phone number
```

Network errors and 429/5xx are retried automatically with backoff. Logic errors
(401/403/404/422) are never retried — repeating them cannot change the answer.

---

## Configuration

```python
client = Client(
    api_key="sk_live_...",
    base_url="http://localhost:3000",   # local development
    timeout=30.0,
    max_retries=2,
)

with Client(api_key="sk_live_...") as client:   # closes the HTTP pool on exit
    ...
```

---

## Versioning

This SDK is pinned to `/api/v1`. A breaking server change ships as `/api/v2`
alongside a major SDK version — `v1` is never changed underneath an installed
client. Unknown response fields are ignored rather than raising, so an additive
server change never breaks an older SDK.

## License

MIT © MTDS
