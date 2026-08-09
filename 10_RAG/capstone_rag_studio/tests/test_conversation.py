"""Feature: rag-studio — conversational chat (multi-turn memory, Req: chatbot UX).

Covers: a conversation persists across turns; the LLM receives a bounded sliding
window of prior turns (not the unbounded full history); messages are durably stored
via SQLite so they survive a simulated restart; a conversation cannot be read or
written by a principal that doesn't own it.
"""
from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager

import pytest

from rag.config import PipelineConfig
from rag.interfaces import AccessPolicy, GenerationOutput, Principal
from rag.pipeline import ConversationNotFoundError, RagStudioPipeline

CONVERSATION_MEMORY_WINDOW = 6


class _CapturingFakeLLM:
    """Records every `history` it was called with; answers deterministically."""

    def __init__(self):
        self.calls: list[list] = []

    def generate(self, question, context_chunks, history=None):
        self.calls.append(list(history or []))
        return GenerationOutput(answer=f"answer to: {question}", citations=[], token_usage=5, cost_estimate=0.0)


@contextmanager
def _pipeline_with_fake_llm():
    import rag.registry as registry

    tmp = tempfile.mkdtemp()
    pipeline = RagStudioPipeline(db_path=f"{tmp}/db.sqlite", upload_dir=f"{tmp}/uploads")
    fake_llm = _CapturingFakeLLM()

    registry.build_llm.cache_clear()
    original_build_llm = registry.build_llm
    registry.build_llm = lambda name, temperature=0.0: fake_llm
    try:
        yield pipeline, fake_llm, tmp
    finally:
        registry.build_llm = original_build_llm
        registry.build_llm.cache_clear()
        shutil.rmtree(tmp, ignore_errors=True)


def _set_up_indexed_variant(pipeline, tmp, name="chat-variant"):
    with open(f"{tmp}/doc.txt", "w") as fh:
        fh.write("Paris is the capital of France.")
    docs = pipeline.ingest_documents([{"path": f"{tmp}/doc.txt", "source": "doc.txt"}], AccessPolicy(access_level="PUBLIC"))
    config = PipelineConfig(name=name, embedding="minilm", vector_store="memory", reranker="none",
                             retrieval="dense", guardrails="off", caching="off")
    pipeline.save_variant(config)
    pipeline.build_index(config, docs)
    return config


def test_conversation_persists_messages_across_turns():
    with _pipeline_with_fake_llm() as (pipeline, fake_llm, tmp):
        _set_up_indexed_variant(pipeline, tmp)
        alice = Principal(id="alice")

        conversation_id = pipeline.start_conversation(alice, "chat-variant")
        pipeline.send_message(alice, conversation_id, "What is the capital of France?")
        pipeline.send_message(alice, conversation_id, "What is it known for?")

        history = pipeline.get_conversation_history(alice, conversation_id)
        roles = [m["role"] for m in history]
        assert roles == ["user", "assistant", "user", "assistant"]
        assert history[0]["content"] == "What is the capital of France?"
        assert "answer to" in history[1]["content"]
        assert history[2]["content"] == "What is it known for?"


def test_llm_receives_bounded_sliding_window_not_full_history():
    with _pipeline_with_fake_llm() as (pipeline, fake_llm, tmp):
        _set_up_indexed_variant(pipeline, tmp)
        alice = Principal(id="alice")
        conversation_id = pipeline.start_conversation(alice, "chat-variant")

        # Send enough turns that full history would exceed the window.
        n_turns = 5
        for i in range(n_turns):
            pipeline.send_message(alice, conversation_id, f"question {i}")

        # The LLM was called once per turn; the LAST call's history must be capped
        # at CONVERSATION_MEMORY_WINDOW messages (not all 2*(n_turns-1) prior messages).
        last_call_history = fake_llm.calls[-1]
        assert len(last_call_history) <= CONVERSATION_MEMORY_WINDOW
        total_prior_messages = 2 * (n_turns - 1)  # user+assistant per completed turn before this one
        assert total_prior_messages > CONVERSATION_MEMORY_WINDOW  # sanity: window really is binding here
        assert len(last_call_history) == CONVERSATION_MEMORY_WINDOW


def test_history_passed_to_llm_reflects_most_recent_turns_in_order():
    with _pipeline_with_fake_llm() as (pipeline, fake_llm, tmp):
        _set_up_indexed_variant(pipeline, tmp)
        alice = Principal(id="alice")
        conversation_id = pipeline.start_conversation(alice, "chat-variant")

        pipeline.send_message(alice, conversation_id, "first")
        pipeline.send_message(alice, conversation_id, "second")

        # The second call's history is exactly [user:"first", assistant:"answer to: first"].
        second_call_history = fake_llm.calls[1]
        assert [t.role for t in second_call_history] == ["user", "assistant"]
        assert second_call_history[0].content == "first"
        assert "first" in second_call_history[1].content


def test_conversation_survives_simulated_restart_via_sqlite():
    with _pipeline_with_fake_llm() as (pipeline, fake_llm, tmp):
        _set_up_indexed_variant(pipeline, tmp)
        alice = Principal(id="alice")
        conversation_id = pipeline.start_conversation(alice, "chat-variant")
        pipeline.send_message(alice, conversation_id, "will this survive?")

        # A brand-new pipeline instance pointed at the same db — simulates a restart.
        restarted = RagStudioPipeline(db_path=f"{tmp}/db.sqlite", upload_dir=f"{tmp}/uploads")

        history = restarted.get_conversation_history(alice, conversation_id)
        assert history[0]["content"] == "will this survive?"


def test_conversation_cannot_be_read_by_a_different_principal():
    with _pipeline_with_fake_llm() as (pipeline, fake_llm, tmp):
        _set_up_indexed_variant(pipeline, tmp)
        alice = Principal(id="alice")
        mallory = Principal(id="mallory")
        conversation_id = pipeline.start_conversation(alice, "chat-variant")
        pipeline.send_message(alice, conversation_id, "secret question")

        with pytest.raises(ConversationNotFoundError):
            pipeline.get_conversation_history(mallory, conversation_id)
        with pytest.raises(ConversationNotFoundError):
            pipeline.send_message(mallory, conversation_id, "trying to hijack")


def test_unknown_conversation_id_raises_not_found():
    with _pipeline_with_fake_llm() as (pipeline, fake_llm, tmp):
        alice = Principal(id="alice")
        with pytest.raises(ConversationNotFoundError):
            pipeline.get_conversation_history(alice, "does-not-exist")
