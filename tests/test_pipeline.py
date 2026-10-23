from datetime import datetime

import httpx
import pytest

from triage import llm
from triage.models import Ticket
from triage.pipeline import TZ, Pipeline, add_business_hours, sla_due

GOOD = {"category": "technical", "priority": "high", "sentiment": "negative", "language": "en",
        "summary": "API down", "draft_reply": "Hi, we're looking into it.", "confidence": 0.9, "reasons": ["api"]}


def at(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)  # Oct 2026: 18 = Sunday


def test_business_hours_within_day():
    assert add_business_hours(at(18, 9), 4) == at(18, 13)


def test_business_hours_roll_to_next_day():
    assert add_business_hours(at(18, 15), 4) == at(19, 10)


def test_business_hours_skip_weekend():
    # Thursday 16:00 + 4h -> 1h on Thursday, then Friday/Saturday off, 3h on Sunday
    assert add_business_hours(at(22, 16), 4) == at(25, 11)


def test_ticket_before_opening_starts_at_8():
    assert add_business_hours(at(19, 6), 1) == at(19, 9)


def test_urgent_ignores_business_hours():
    assert sla_due("urgent", at(23, 22)) == at(23, 23)


def test_urgent_and_negative_need_review():
    r = Pipeline("rules").run(Ticket(id="1", body="Everything is down for all users, terrible"))
    assert r.needs_review and r.team == "Tier 2 – Engineering"


def test_llm_failure_falls_back_to_rules(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = Pipeline("openai").run(Ticket(id="1", body="invoice please"))
    assert r.engine == "rules" and r.fallback_reason and r.needs_review


def test_openai_structured_output_parsed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    body = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": __import__("json").dumps(GOOD)}]}]}
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=body))
    res = llm.classify_openai(Ticket(id="1", body="api down"), client=httpx.Client(transport=transport))
    assert res.category == "technical" and res.confidence == 0.9


def test_openai_invalid_enum_rejected():
    body = {"status": "completed", "output": [{"content": [{"type": "output_text",
            "text": __import__("json").dumps({**GOOD, "category": "sales"})}]}]}
    with pytest.raises(llm.LLMError):
        llm.parse_openai(body)


def test_openai_refusal_and_incomplete_fail_closed():
    for body in [{"status": "incomplete"}, {"status": "completed", "output": [{"content": [{"type": "refusal"}]}]}]:
        with pytest.raises(llm.LLMError):
            llm.parse_openai(body)


def test_anthropic_tool_call_parsed(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    body = {"content": [{"type": "text", "text": "ok"}, {"type": "tool_use", "name": "record_triage", "input": GOOD}]}
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=body))
    res = llm.classify_anthropic(Ticket(id="1", body="x"), client=httpx.Client(transport=transport))
    assert res.priority == "high"


def test_http_error_is_llm_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    transport = httpx.MockTransport(lambda req: httpx.Response(429, json={}))
    with pytest.raises(llm.LLMError, match="429"):
        llm.classify_openai(Ticket(id="1", body="x"), client=httpx.Client(transport=transport))
