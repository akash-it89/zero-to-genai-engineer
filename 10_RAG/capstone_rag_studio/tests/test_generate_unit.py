"""Feature: rag-studio — generation unit/example tests (mocked LLM, Req 5, 9, 14).

Covers: the prompt contains only the supplied context chunks; insufficient context
yields the not-found phrase; an OpenRouter selection is invoked through the OpenAI-
compatible endpoint; a missing required key and a provider-call failure each surface
a descriptive structured error with no key value; prior conversation turns are
threaded through as real chat messages for conversational chat.
"""
from __future__ import annotations

import types

import pytest

from rag.generate import (
    GenerationProviderError,
    MissingApiKeyError,
    NOT_FOUND_TEXT,
    OpenAIGenerationLLM,
    OpenRouterGenerationLLM,
    _build_messages,
)
from rag.interfaces import Chunk, ConversationTurn


def _fake_openai_client(captured: dict, answer: str = "The sky is blue [c1]."):
    """A stand-in for `openai.OpenAI()` recording the request it received."""

    class _Message:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.message = _Message(content)

    class _Usage:
        total_tokens = 42

    class _Response:
        def __init__(self, content):
            self.choices = [_Choice(content)]
            self.usage = _Usage()

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Response(answer)

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class _Client:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = _Chat()

    return _Client


def test_prompt_contains_only_supplied_context_chunks():
    chunks = [Chunk(id="c1", text="Paris is the capital of France.", source="doc1")]
    messages = _build_messages("What is the capital of France?", chunks)
    system_message = messages[0]["content"]
    assert "Paris is the capital of France." in system_message
    assert "c1" in system_message
    # The question itself is the final user message, not folded into the system prompt.
    assert messages[-1] == {"role": "user", "content": "What is the capital of France?"}


def test_prompt_instructs_not_found_phrase_when_no_context():
    messages = _build_messages("Unanswerable question?", [])
    system_message = messages[0]["content"]
    assert NOT_FOUND_TEXT in system_message
    assert "(no context chunks supplied)" in system_message


def test_history_is_threaded_through_as_real_chat_messages_between_system_and_question():
    chunks = [Chunk(id="c1", text="Some fact.", source="doc1")]
    history = [
        ConversationTurn(role="user", content="What is Paris known for?"),
        ConversationTurn(role="assistant", content="The Eiffel Tower [c1]."),
    ]
    messages = _build_messages("What about its population?", chunks, history)

    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "What is Paris known for?"}
    assert messages[2] == {"role": "assistant", "content": "The Eiffel Tower [c1]."}
    assert messages[3] == {"role": "user", "content": "What about its population?"}
    assert len(messages) == 4


def test_no_history_is_a_true_no_op_matching_stateless_single_shot_behavior():
    chunks = [Chunk(id="c1", text="Some fact.", source="doc1")]
    with_none = _build_messages("Q?", chunks, None)
    with_empty = _build_messages("Q?", chunks, [])
    assert with_none == with_empty
    assert len(with_none) == 2  # system + the single question, no history turns


def test_openai_llm_generates_and_extracts_citation(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured: dict = {}
    fake_module = types.SimpleNamespace(OpenAI=_fake_openai_client(captured))
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_module)

    chunks = [Chunk(id="c1", text="Some fact.", source="doc1")]
    llm = OpenAIGenerationLLM(model="gpt-4o-mini", temperature=0.0)
    result = llm.generate("A question?", chunks)

    assert result.answer == "The sky is blue [c1]."
    assert result.token_usage == 42
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "c1"
    assert result.citations[0].source == "doc1"
    # The request used the configured model.
    assert captured["model"] == "gpt-4o-mini"


def test_citation_extraction_never_cites_a_chunk_outside_supplied_context():
    from rag.generate import _extract_citations

    supplied = [Chunk(id="c1", text="in context", source="doc1")]
    # The model hallucinates a reference to a chunk id never supplied.
    citations = _extract_citations("Answer citing [c1] and [zzz-not-supplied].", supplied)
    assert [c.chunk_id for c in citations] == ["c1"]


def test_openai_llm_missing_key_raises_without_leaking_value(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = OpenAIGenerationLLM(model="gpt-4o-mini")
    with pytest.raises(MissingApiKeyError) as exc_info:
        llm.generate("Q?", [])
    assert exc_info.value.env_key == "OPENAI_API_KEY"
    assert "sk-" not in str(exc_info.value)


def test_openrouter_llm_invoked_through_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured: dict = {}
    fake_module = types.SimpleNamespace(OpenAI=_fake_openai_client(captured))
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_module)

    llm = OpenRouterGenerationLLM(model="anthropic/claude-3.5-sonnet", temperature=0.0)
    result = llm.generate("Q?", [])

    assert result.answer == "The sky is blue [c1]."
    assert captured["client_kwargs"]["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["client_kwargs"]["api_key"] == "sk-or-test"


def test_openrouter_llm_missing_key_raises_without_leaking_value(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    llm = OpenRouterGenerationLLM(model="anthropic/claude-3.5-sonnet")
    with pytest.raises(MissingApiKeyError) as exc_info:
        llm.generate("Q?", [])
    assert exc_info.value.env_key == "OPENROUTER_API_KEY"
    assert "sk-or-" not in str(exc_info.value)


def test_provider_call_failure_wrapped_with_module_name_no_key_value(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value")

    class _RaisingCompletions:
        def create(self, **kwargs):
            raise RuntimeError("upstream 500: rate limited")

    class _RaisingChat:
        def __init__(self):
            self.completions = _RaisingCompletions()

    class _RaisingClient:
        def __init__(self, **kwargs):
            self.chat = _RaisingChat()

    fake_module = types.SimpleNamespace(OpenAI=_RaisingClient)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_module)

    llm = OpenAIGenerationLLM(model="gpt-4o-mini")
    with pytest.raises(GenerationProviderError) as exc_info:
        llm.generate("Q?", [])
    message = str(exc_info.value)
    assert "rag.generate.OpenAIGenerationLLM" in message
    assert "rate limited" in message
    assert "sk-super-secret-value" not in message
