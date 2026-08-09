"""Feature: rag-studio — evaluation unit/example tests (mocked judge, Req 7, 8).

Covers: RAGAS-vs-DeepEval framework selection routes to the chosen adapter; DeepEval
surfaces pass/fail outcome + human-readable reason; an evaluation that cannot
complete returns a descriptive error and leaves prior results untouched.
"""
from __future__ import annotations

import pytest

from rag.evaluation import (
    DeepEvalEvaluationFramework,
    EvaluationError,
    RagasEvaluationFramework,
    make_evaluation_framework,
)

SAMPLES = [
    {"id": "s1", "question": "What is the capital of France?", "answer": "Paris.",
     "contexts": ["Paris is the capital of France."], "reference": "Paris"},
    {"id": "s2", "question": "What is 2+2?", "answer": "4.", "contexts": ["2+2=4"]},
]


def test_make_evaluation_framework_routes_to_ragas():
    assert isinstance(make_evaluation_framework("ragas"), RagasEvaluationFramework)


def test_make_evaluation_framework_routes_to_deepeval():
    assert isinstance(make_evaluation_framework("deepeval"), DeepEvalEvaluationFramework)


def test_make_evaluation_framework_unknown_name_raises():
    with pytest.raises(ValueError):
        make_evaluation_framework("not-a-real-framework")


def test_ragas_evaluate_averages_reference_free_scores(monkeypatch):
    def fake_call_ragas(samples, metrics):
        return {m: [0.8, 0.6][: len(samples)] for m in metrics}

    monkeypatch.setattr("rag.evaluation._call_ragas", fake_call_ragas)
    framework = RagasEvaluationFramework()
    result = framework.evaluate(SAMPLES, metrics=["faithfulness"])
    assert result.scores["faithfulness"] == pytest.approx(0.7)


def test_deepeval_surfaces_pass_fail_and_reason(monkeypatch):
    def fake_call_deepeval(samples, metrics):
        scores = {m: [0.9, 0.2] for m in metrics}
        passed = {m: [True, False] for m in metrics}
        reasons = {m: ["good faithfulness", "hallucinated a detail"] for m in metrics}
        return scores, passed, reasons

    monkeypatch.setattr("rag.evaluation._call_deepeval", fake_call_deepeval)
    framework = DeepEvalEvaluationFramework()
    result = framework.evaluate(SAMPLES, metrics=["faithfulness"])

    assert result.passed["faithfulness"] is False   # not every sample passed
    assert "hallucinated a detail" in result.reasons["faithfulness"]
    assert result.scores["faithfulness"] == pytest.approx(0.55)


def test_deepeval_all_samples_pass_gives_true_and_summary_reason(monkeypatch):
    def fake_call_deepeval(samples, metrics):
        scores = {m: [0.95, 0.9] for m in metrics}
        passed = {m: [True, True] for m in metrics}
        reasons = {m: ["fine", "fine"] for m in metrics}
        return scores, passed, reasons

    monkeypatch.setattr("rag.evaluation._call_deepeval", fake_call_deepeval)
    framework = DeepEvalEvaluationFramework()
    result = framework.evaluate(SAMPLES, metrics=["answer_relevancy"])

    assert result.passed["answer_relevancy"] is True
    assert result.reasons["answer_relevancy"] == "all samples passed"


def test_ragas_evaluation_failure_raises_descriptive_error_not_a_crash(monkeypatch):
    def failing_call_ragas(samples, metrics):
        raise RuntimeError("judge LLM timed out")

    monkeypatch.setattr("rag.evaluation._call_ragas", failing_call_ragas)
    framework = RagasEvaluationFramework()
    with pytest.raises(RuntimeError):
        framework.evaluate(SAMPLES, metrics=["faithfulness"])


def test_evaluation_error_names_framework_and_message():
    err = EvaluationError("ragas", "judge LLM timed out")
    assert "ragas" in str(err)
    assert "judge LLM timed out" in str(err)
