"""Standalone backend server with all provider I/O mocked, for Playwright e2e tests.

Not part of the production backend — started by the frontend's `test:e2e` script
(via Playwright's `webServer` config) alongside the Vite dev server, so the SPA's
functional tests exercise real HTTP requests against a real (but provider-mocked)
backend and a fixed on-disk corpus, per project convention (provider I/O is mocked
in every test layer; only the capstone notebook makes live calls).
"""
from __future__ import annotations

import os
import tempfile

import uvicorn

import rag.registry as registry
from rag.interfaces import GenerationOutput, MetricScores
from rag.pipeline import RagStudioPipeline


class _FakeGenerationLLM:
    def generate(self, question, context_chunks, history=None):
        citation = f" [{context_chunks[0].id}]" if context_chunks else ""
        return GenerationOutput(
            answer=f"Answer to '{question}'{citation}", citations=[], token_usage=10, cost_estimate=0.001
        )


class _FakeEvaluationFramework:
    """Deterministic stand-in for RAGAS/DeepEval — no judge LLM call, no network."""

    def evaluate(self, samples, metrics, reference=False):
        result = MetricScores()
        for m in metrics:
            result.scores[m] = 0.83
            result.passed[m] = True
            result.reasons[m] = "deterministic mocked judge: looks faithful and relevant"
        without_ref = [s.get("id", str(i)) for i, s in enumerate(samples) if not s.get("reference")]
        if reference:
            result.excluded_reference_dependent = without_ref
        return result


def _install_mocks() -> None:
    registry.build_llm.cache_clear()
    registry.build_evaluation_framework.cache_clear()
    registry.build_llm = lambda name, temperature=0.0: _FakeGenerationLLM()
    registry.build_evaluation_framework = lambda name: _FakeEvaluationFramework()


_OPTIONAL_KEYS = ("OPENROUTER_API_KEY", "COHERE_API_KEY", "PINECONE_API_KEY")


def main() -> None:
    _install_mocks()
    tmp = tempfile.mkdtemp(prefix="rag_studio_e2e_")
    os.environ.setdefault("RAG_STUDIO_DB_PATH", f"{tmp}/db.sqlite")
    os.environ.setdefault("RAG_STUDIO_UPLOAD_DIR", f"{tmp}/uploads")
    os.environ.setdefault("RAG_STUDIO_CORS_ORIGINS", "http://localhost:5173")

    from backend.main import create_app  # triggers backend.main's load_dotenv(10_RAG/.env)

    # e2e must be deterministic regardless of what the developer's real .env
    # contains — force every optional (key-gated) provider back to "unavailable"
    # so reserved/unavailable-option assertions don't depend on local secrets.
    for key in _OPTIONAL_KEYS:
        os.environ.pop(key, None)

    pipeline = RagStudioPipeline(
        db_path=os.environ["RAG_STUDIO_DB_PATH"], upload_dir=os.environ["RAG_STUDIO_UPLOAD_DIR"]
    )
    app = create_app(pipeline=pipeline)
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("RAG_STUDIO_E2E_PORT", "8000")))


if __name__ == "__main__":
    main()
