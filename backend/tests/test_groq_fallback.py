"""Gemini unavailable -> Groq answers with the same grounding rules -> template if Groq fails too."""

import pytest

from app.ai import copilot, groq_client
from app.config import get_settings
from tests.conftest import COORD, add_units, headers

pytestmark = pytest.mark.db


@pytest.fixture
def groq_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", "test-key")
    yield
    monkeypatch.setattr(get_settings(), "groq_api_key", None)


async def test_copilot_uses_groq_with_tools_when_gemini_down(client, db, groq_on, monkeypatch):
    async with db() as s:
        add_units(s, 1, "O-", "RBC", 3)
        await s.commit()
    calls = []

    async def fake_chat(messages, tools=None, json_mode=False, **kw):
        calls.append(messages)
        if len(calls) == 1:  # first turn: ask for a tool
            return {"content": "", "tool_calls": [{"id": "c1", "type": "function",
                    "function": {"name": "get_facility_inventory", "arguments": '{"facility": "H-1"}'}}]}
        tool_msg = next(m for m in messages if m.get("role") == "tool")
        assert '"O- RBC": 3' in tool_msg["content"]  # real DB value reached the model
        return {"content": "Hospital One has 3 units of O- RBC available."}

    monkeypatch.setattr(groq_client, "chat", fake_chat)
    r = await client.post("/api/copilot/chat", json={"message": "How much O- does H-1 have?"}, headers=headers(COORD()))
    body = r.json()
    assert body["provider"] == "groq" and not body["fallback"] and "get_facility_inventory" in body["tools_used"]


async def test_groq_hallucination_is_rejected(client, db, groq_on, monkeypatch):
    async def fake_chat(messages, tools=None, json_mode=False, **kw):
        return {"content": "There are 999 units of O- everywhere."}  # never grounded

    monkeypatch.setattr(groq_client, "chat", fake_chat)
    body = (await client.post("/api/copilot/chat", json={"message": "status?"}, headers=headers(COORD()))).json()
    assert body["provider"] == "template" and body["fallback"]


async def test_groq_outage_falls_back_to_template(client, db, groq_on, monkeypatch):
    async def boom(*a, **k):
        raise groq_client.GroqUnavailable("down")

    monkeypatch.setattr(groq_client, "chat", boom)
    body = (await client.post("/api/copilot/chat", json={"message": "show open alerts"}, headers=headers(COORD()))).json()
    assert body["provider"] == "template" and "list_alerts" in body["tools_used"]


def test_meta_reports_groq(groq_on):
    assert groq_client.status()["enabled"] and copilot.chat_groq
