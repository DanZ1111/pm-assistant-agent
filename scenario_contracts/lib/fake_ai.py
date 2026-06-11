"""Queue-driven fake OpenAI client for deterministic AI testing.

Extracted from test_build21.py:36-86 so QA-08+ journey scenarios can
inject AI responses without an LLM. QA-05 contracts test `dispatch`
directly and do not use this library; the library lands now because
journeys need it.

Public API:
  fake = FakeOpenAIClient()
  fake.chat.completions.queue_text("plain reply")
  fake.chat.completions.queue_tool_call(
      name="create_idea",
      args_dict={"name": "New mechanism idea"},
      follow_text="I propose creating an idea.",
  )
  # Inject into the production client slot:
  from scenario_contracts.lib.fake_ai import install
  install(fake)
"""
from __future__ import annotations

import json


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments  # JSON string, mirrors OpenAI shape


class _FakeToolCall:
    def __init__(self, name, arguments):
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeResponse:
    def __init__(self, content, tool_calls=None):
        self.choices = [_FakeChoice(_FakeMessage(content, tool_calls))]


class _FakeCompletions:
    """FIFO queue. Each create() call pops the next queued response."""

    def __init__(self):
        self._queue = []

    def queue_text(self, content):
        """Queue a plain text reply with no tool call."""
        self._queue.append((content, None))

    def queue_tool_call(self, name, args_dict, follow_text=""):
        """Queue a tool-call proposal. The model would normally emit
        an assistant message with `tool_calls=[...]` and (optionally)
        a brief text describing what it's about to do.
        """
        tc = _FakeToolCall(name, json.dumps(args_dict))
        self._queue.append((follow_text, [tc]))

    def create(self, **kwargs):
        if not self._queue:
            return _FakeResponse("(no response queued)")
        content, tool_calls = self._queue.pop(0)
        return _FakeResponse(content, tool_calls)


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class FakeOpenAIClient:
    """Public name; mirrors openai.OpenAI() shape closely enough for the
    `client.chat.completions.create(...)` call path used by the app.
    """

    def __init__(self):
        self.chat = _FakeChat()


def install(client):
    """Monkey-patch the production client slot used by `app/routes/ai_chat.py`.

    Returns the previous client so callers can restore it on teardown.
    """
    from app.routes import ai_chat

    previous = getattr(ai_chat, "_client", None)
    ai_chat._client = client
    return previous
