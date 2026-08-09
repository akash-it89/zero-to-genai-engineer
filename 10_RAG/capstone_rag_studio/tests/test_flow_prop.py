"""Feature: rag-studio — cross-stage no-op / secret-safety property tests.

Part 1: P15 — `query_transform=none` and `post_retrieval=none` are true identity
no-ops (Req 20.4).
Part 2 (this wave): P15's `guardrails=off` leg, and P22 secret/removed-chunk-content
non-disclosure (safety-critical, elevated example count — Req 11.14, 18.2-18.6,
19.6, 24.1-24.3, 24.5).
"""
from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from rag.interfaces import AnswerResult, Chunk, PipelineContext, Principal, Trace
from rag.post_retrieval import make_post_retrieval_processor
from rag.query_transform import make_query_transformer

questions = st.text(min_size=1, max_size=40)
chunk_texts = st.lists(st.text(min_size=0, max_size=80), max_size=6)
ELEVATED = settings(max_examples=300)


@given(question=questions)
@settings(max_examples=100)
def test_p15_query_transform_none_is_identity(question):
    transformer = make_query_transformer("none")
    ctx = PipelineContext(config=None, principal=Principal(id="u1"))
    plan = transformer.transform(question, ctx)
    assert plan.queries == [question]
    assert plan.embed_texts is None
    assert plan.merge is False


@given(question=questions, texts=chunk_texts)
@settings(max_examples=100)
def test_p15_post_retrieval_none_is_identity(question, texts):
    processor = make_post_retrieval_processor("none")
    chunks = [Chunk(id=f"c{i}", text=t, source="doc1") for i, t in enumerate(texts)]
    ctx = PipelineContext(config=None, principal=Principal(id="u1"))
    result = processor.process(question, chunks, ctx)
    assert result == chunks
    assert [c.text for c in result] == texts


# ---------------------------------------------------------------------------
# P15 (guardrails=off leg) — identity no-op (Req 20.4)
# ---------------------------------------------------------------------------

from rag.guardrails import make_guardrail

texts = st.text(min_size=0, max_size=200)


@given(text=texts)
@settings(max_examples=100)
def test_p15_guardrail_off_input_is_identity(text):
    guardrail = make_guardrail("off")
    verdict = guardrail.screen_input(text)
    assert verdict.allowed is True
    assert verdict.flagged is False
    assert verdict.text == text


@given(text=texts)
@settings(max_examples=100)
def test_p15_guardrail_off_output_is_identity(text):
    guardrail = make_guardrail("off")
    verdict = guardrail.screen_output(text)
    assert verdict.allowed is True
    assert verdict.flagged is False
    assert verdict.text == text


# ---------------------------------------------------------------------------
# P22 — secrets / removed-chunk content never disclosed (safety-critical)
# ---------------------------------------------------------------------------

import contextlib
import os

from rag import registry as R
from rag.cache import ExactMatchCache
from rag.generate import MissingApiKeyError as GenMissingKeyError
from rag.generate import OpenAIGenerationLLM

# A hex-like alphabet — long enough and distinct enough from any real catalog label
# (e.g. "Orchestrator") that it can never collide by chance (Req 24.3).
secret_values = st.text(alphabet="0123456789abcdef", min_size=20, max_size=32)

_SECRET_ENV_KEYS = ["OPENROUTER_API_KEY", "COHERE_API_KEY", "PINECONE_API_KEY"]


@contextlib.contextmanager
def _env_secret(secret: str, present: list[str], absent: list[str] = ()):
    """Set `present` Env_Keys to `secret`, ensure `absent` are unset; restore after.

    A plain context manager (not the monkeypatch fixture) since Hypothesis re-runs the
    test body many times per invocation and function-scoped fixtures are not reset
    between runs (see tests/test_registry_prop.py's `env_only`).
    """
    keys = list(present) + list(absent)
    saved = {k: os.environ.get(k) for k in keys}
    try:
        for k in present:
            os.environ[k] = secret
        for k in absent:
            os.environ.pop(k, None)
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@given(secret=secret_values)
@ELEVATED
def test_p22_options_catalog_never_leaks_env_key_values(secret):
    with _env_secret(secret, present=_SECRET_ENV_KEYS):
        snapshot_json = json.dumps(R.options_snapshot())
    assert secret not in snapshot_json
    # The key NAME is present (so the UI can explain what's missing), never the value.
    assert "OPENROUTER_API_KEY" in snapshot_json


@given(secret=secret_values)
@ELEVATED
def test_p22_missing_key_errors_never_leak_a_present_secret_elsewhere(secret):
    # Simulate: COHERE_API_KEY holds a secret, but OPENAI_API_KEY (needed here) is absent.
    with _env_secret(secret, present=["COHERE_API_KEY"], absent=["OPENAI_API_KEY"]):
        llm = OpenAIGenerationLLM(model="gpt-4o-mini")
        try:
            llm.generate("Q?", [])
            raised = None
        except GenMissingKeyError as exc:
            raised = exc
    assert raised is not None
    assert secret not in str(raised)


@given(secret=secret_values)
@ELEVATED
def test_p22_answer_result_and_trace_carry_no_content_field_for_removed_chunks(secret):
    # Structural guarantee: neither dataclass has any field that could hold removed
    # chunk content — only a count (Req 11.14, 19.6). A hypothesis-generated secret
    # standing in for "removed chunk content" can never appear in a serialized result
    # because there is no field to put it in.
    result = AnswerResult(variant_name="v1", answer="the answer", governance_filtered_count=3)
    trace = Trace(request_id="r1", variant_name="v1", governance_filtered_count=3)

    result_field_names = set(AnswerResult.__dataclass_fields__.keys())
    trace_field_names = set(Trace.__dataclass_fields__.keys())
    assert not any("removed" in f or "filtered_chunk" in f for f in result_field_names)
    assert not any("removed" in f or "filtered_chunk" in f for f in trace_field_names)
    assert secret not in json.dumps({"answer": result.answer, "citations": result.citations,
                                      "stages": trace.stages}, default=str)


@given(secret=secret_values)
@ELEVATED
def test_p22_ui_submitted_key_fields_are_ignored_no_such_field_exists(secret):
    # The backend/UI can never submit a key value because PipelineConfig has no field
    # that could carry one (Req 24.1) — the only source of keys is the environment.
    from rag.config import PipelineConfig

    assert not any("key" in f.lower() for f in PipelineConfig.field_names())
    # Even constructing an ExactMatchCache key from a config dict smuggling a fake
    # "api_key" entry never surfaces the secret in the resulting cache key itself
    # being unusable as a real credential (it's just hashed away).
    cache = ExactMatchCache()
    key = cache.key(Principal(id="u1"), {"api_key": secret}, "question")
    assert secret not in key
