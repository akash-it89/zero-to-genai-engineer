"""Feature: rag-studio — backend integration tests (FastAPI TestClient, mocked providers).

End-to-end through the real façade: ingest -> index -> save variant -> POST /chat
returns cited side-by-side results and a retrievable GET /trace/{id}; a raising
variant is isolated while others still return; missing Acting_Principal is rejected
before any data error; unknown-variant and index-not-built errors are returned, with
the ingestion error preferred when both no-variant and no-index hold.
(Req 6.1, 6.4, 6.7, 14.2, 14.4, 14.5, 14.6, 14.7, 19.2)
"""
from __future__ import annotations

import contextlib
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from rag.interfaces import GenerationOutput
from rag.pipeline import RagStudioPipeline

HEADERS = {"X-Principal-Id": "alice"}


class _FakeGenerationLLM:
    """A deterministic, free stand-in for a real provider LLM (all provider I/O mocked)."""

    def generate(self, question, context_chunks, history=None):
        citation_ids = [c.id for c in context_chunks[:1]]
        answer = f"Answer to '{question}'" + (f" [{citation_ids[0]}]" if citation_ids else "")
        return GenerationOutput(answer=answer, citations=[], token_usage=10, cost_estimate=0.001)


class _RaisingReranker:
    """Deterministically fails at run time — stands in for a real reranker outage
    without making any network call."""

    def rerank(self, question, chunks, top_k):
        raise RuntimeError("simulated reranker outage")


@contextlib.contextmanager
def _mocked_client():
    tmp = tempfile.mkdtemp()
    pipeline = RagStudioPipeline(db_path=f"{tmp}/db.sqlite", upload_dir=f"{tmp}/uploads")

    # Mock provider I/O: local embedder (no API key needed), a fake LLM, and a fake
    # "cohere" reranker that fails deterministically (no real network call).
    import rag.registry as registry

    registry.build_llm.cache_clear()
    registry.build_reranker.cache_clear()
    original_build_llm = registry.build_llm
    original_build_reranker = registry.build_reranker
    registry.build_llm = lambda name, temperature=0.0: _FakeGenerationLLM()
    registry.build_reranker = lambda name: _RaisingReranker() if name == "cohere" else original_build_reranker(name)

    app = create_app(pipeline=pipeline)
    client = TestClient(app)
    try:
        yield client, pipeline, tmp
    finally:
        registry.build_llm = original_build_llm
        registry.build_reranker = original_build_reranker
        registry.build_llm.cache_clear()
        registry.build_reranker.cache_clear()


def _save_and_index_variant(client, tmp, name="v1", **overrides):
    config = {"name": name, "embedding": "minilm", "vector_store": "memory",
              "reranker": "none", "retrieval": "dense", "guardrails": "off",
              "caching": "off", **overrides}
    resp = client.post("/variants", json=config, headers=HEADERS)
    assert resp.status_code == 200, resp.text

    with open(f"{tmp}/doc1.txt", "w") as fh:
        fh.write("Paris is the capital of France. " * 5)
    with open(f"{tmp}/doc1.txt", "rb") as fh:
        resp = client.post(
            "/ingest",
            files={"files": ("doc1.txt", fh, "text/plain")},
            data={"access_level": "PUBLIC"},
            headers=HEADERS,
        )
    assert resp.status_code == 200, resp.text

    resp = client.post("/index", json={"variant_name": name}, headers=HEADERS)
    assert resp.status_code == 200, resp.text
    return config


def test_full_flow_ingest_index_save_chat_and_trace():
    with _mocked_client() as (client, pipeline, tmp):
        _save_and_index_variant(client, tmp)

        resp = client.post("/chat", json={"question": "What is the capital of France?"}, headers=HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "v1" in body["results"]
        assert not body["errors"]

        result = body["results"]["v1"]
        assert "Answer to" in result["answer"]
        assert result["trace_id"]

        trace_resp = client.get(f"/trace/{result['trace_id']}", headers=HEADERS)
        assert trace_resp.status_code == 200, trace_resp.text
        trace = trace_resp.json()
        assert trace["stages"]
        stage_names = [s["stage"] for s in trace["stages"]]
        assert "generate" in stage_names


def test_raising_variant_is_isolated_while_others_still_return(monkeypatch):
    # A fake key so config validation (availability check) passes at save time; the
    # actual "cohere" reranker is swapped for a deterministically-raising fake below.
    monkeypatch.setenv("COHERE_API_KEY", "fake-key-for-validation-only")
    with _mocked_client() as (client, pipeline, tmp):
        _save_and_index_variant(client, tmp, name="good")
        # A second variant whose reranker fails at run time.
        _save_and_index_variant(client, tmp, name="bad", reranker="cohere")

        resp = client.post("/chat", json={"question": "What is the capital of France?"}, headers=HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert "good" in body["results"]
        assert "bad" in body["errors"]
        assert "bad" not in body["results"]
        assert "good" not in body["errors"]


def test_missing_principal_rejected_before_any_data_error():
    with _mocked_client() as (client, pipeline, tmp):
        # No X-Principal-Id header at all, and a request body that would otherwise 400.
        resp = client.post("/chat", json={})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_unknown_variant_error_when_docs_exist_but_variant_does_not():
    with _mocked_client() as (client, pipeline, tmp):
        _save_and_index_variant(client, tmp, name="v1")

        resp = client.post("/chat", json={"question": "Q?", "variant_names": ["does-not-exist"]}, headers=HEADERS)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "UNKNOWN_VARIANT"


def test_index_not_built_error_when_variant_exists_but_unindexed():
    with _mocked_client() as (client, pipeline, tmp):
        _save_and_index_variant(client, tmp, name="v1")  # this ingests docs + builds v1's index

        # A second variant is saved but never indexed.
        resp = client.post("/variants", json={"name": "v2", "embedding": "minilm"}, headers=HEADERS)
        assert resp.status_code == 200

        resp = client.post("/chat", json={"question": "Q?", "variant_names": ["v2"]}, headers=HEADERS)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INDEX_NOT_BUILT"


def test_ingestion_error_preferred_when_both_no_variant_and_no_index_hold():
    with _mocked_client() as (client, pipeline, tmp):
        # Nothing has ever been ingested or indexed, and the variant doesn't exist either.
        resp = client.post("/chat", json={"question": "Q?", "variant_names": ["ghost"]}, headers=HEADERS)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "NO_DOCUMENTS_INGESTED"


def test_conversation_endpoints_multi_turn_with_history_and_ownership():
    with _mocked_client() as (client, pipeline, tmp):
        _save_and_index_variant(client, tmp, name="chatbot-v1")

        resp = client.post("/conversations", json={"variant_name": "chatbot-v1"}, headers=HEADERS)
        assert resp.status_code == 200, resp.text
        conversation_id = resp.json()["conversation_id"]

        resp = client.post(
            f"/conversations/{conversation_id}/messages", json={"content": "What is the capital of France?"}, headers=HEADERS
        )
        assert resp.status_code == 200, resp.text
        assert "Answer to" in resp.json()["answer"]

        resp = client.post(
            f"/conversations/{conversation_id}/messages", json={"content": "Tell me more."}, headers=HEADERS
        )
        assert resp.status_code == 200, resp.text

        resp = client.get(f"/conversations/{conversation_id}/messages", headers=HEADERS)
        assert resp.status_code == 200, resp.text
        messages = resp.json()["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
        assert messages[0]["content"] == "What is the capital of France?"

        resp = client.get("/conversations", headers=HEADERS)
        assert resp.status_code == 200
        assert any(c["id"] == conversation_id for c in resp.json())

        # A different principal cannot read or post to this conversation.
        other_headers = {"X-Principal-Id": "mallory"}
        resp = client.get(f"/conversations/{conversation_id}/messages", headers=other_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

        resp = client.post(f"/conversations/{conversation_id}/messages", json={"content": "hijack"}, headers=other_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_evaluate_retrieval_scores_perfect_recall_for_the_only_matching_doc():
    with _mocked_client() as (client, pipeline, tmp):
        _save_and_index_variant(client, tmp, name="v1")   # indexes doc1.txt: "Paris is the capital of France."

        resp = client.post(
            "/evaluate/retrieval",
            json={
                "golden_set": [{"question": "What is the capital of France?", "expected_sources": ["doc1.txt"]}],
                "variant_names": ["v1"],
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert not body["errors"]
        overall = body["results"]["v1"]["overall"]
        # Only one document was ever ingested, so it must be the top retrieved chunk.
        assert overall["r@1"] == pytest.approx(1.0)
        assert overall["r@3"] == pytest.approx(1.0)
        assert overall["mrr@10"] == pytest.approx(1.0)


def test_evaluate_retrieval_by_query_type_breakdown():
    with _mocked_client() as (client, pipeline, tmp):
        _save_and_index_variant(client, tmp, name="v1")

        resp = client.post(
            "/evaluate/retrieval",
            json={
                "golden_set": [
                    {"question": "What is the capital of France?", "expected_sources": ["doc1.txt"], "query_type": "semantic"},
                    {"question": "capital France", "expected_sources": ["doc1.txt"], "query_type": "keyword"},
                ],
                "variant_names": ["v1"],
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        by_type = resp.json()["results"]["v1"]["by_query_type"]
        assert set(by_type.keys()) == {"semantic", "keyword"}


def test_evaluate_retrieval_isolates_failing_variant():
    import os

    os.environ.setdefault("COHERE_API_KEY", "fake-key-for-validation-only")
    with _mocked_client() as (client, pipeline, tmp):
        _save_and_index_variant(client, tmp, name="good")
        _save_and_index_variant(client, tmp, name="bad", reranker="cohere")

        resp = client.post(
            "/evaluate/retrieval",
            json={
                "golden_set": [{"question": "What is the capital of France?", "expected_sources": ["doc1.txt"]}],
                "variant_names": ["good", "bad"],
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "good" in body["results"]
        assert "bad" in body["errors"]
        assert "bad" not in body["results"]
