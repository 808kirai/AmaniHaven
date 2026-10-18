import json

import anthropic
import httpx2 as httpx
import pytest

from app.triage import llm

from .conftest import run

# checks the claude request shape and failure handling without touching the network


def fake_client(handler):
    return anthropic.AsyncAnthropic(api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def message(text, stop_reason="end_turn"):
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}] if text else [],
        "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


@pytest.fixture
def use_client(monkeypatch):
    def install(handler):
        monkeypatch.setattr(llm, "_client", fake_client(handler))

    yield install
    llm._client = None


def test_request_shape_and_parse(use_client):
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        verdict = {"tier": "crisis", "topics": ["grief"], "ask_safety_question": False, "reason": "Coded farewell"}
        return httpx.Response(200, json=message(json.dumps(verdict)))

    use_client(handler)
    out = run(llm.classify("nimewaaga wote, kwaheri", ["mama alifariki"]))

    assert out.tier == "crisis" and out.topics == ["grief"]
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "<earlier>mama alifariki</earlier>" in body["messages"][0]["content"]
    assert "+254" not in json.dumps(body)  # no identifiers leave the system


def test_refusal_returns_none(use_client):
    use_client(lambda r: httpx.Response(200, json=message("", stop_reason="refusal")))
    assert run(llm.classify("text", [])) is None


def test_outage_returns_none(use_client):
    use_client(lambda r: httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "x"}}))
    assert run(llm.classify("text", [])) is None


def test_connection_error_returns_none(use_client):
    def handler(request):
        raise httpx.ConnectError("down")

    use_client(handler)
    assert run(llm.classify("text", [])) is None
