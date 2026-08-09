"""Feature: rag-studio — evaluation property test (Req 8.8).

Covers design property P24: golden records without a ground-truth reference are
excluded from reference-dependent metrics (and the exclusion is reported), while
reference-free metrics still apply to every record regardless.
"""
from __future__ import annotations

import contextlib

import rag.evaluation as evaluation_module
from hypothesis import given, settings
from hypothesis import strategies as st

from rag.evaluation import RagasEvaluationFramework

questions = st.text(min_size=1, max_size=20)


@contextlib.contextmanager
def _fake_call_ragas(calls: list):
    """Patches `_call_ragas` via a plain context manager (not the monkeypatch fixture)
    since Hypothesis re-runs the test body many times per invocation and function-
    scoped fixtures are not reset between runs (see test_registry_prop.py's `env_only`)."""

    def _fake(samples, metrics):
        calls.append((list(samples), list(metrics)))
        return {m: [1.0] * len(samples) for m in metrics}

    original = evaluation_module._call_ragas
    evaluation_module._call_ragas = _fake
    try:
        yield
    finally:
        evaluation_module._call_ragas = original


@given(
    n_with_ref=st.integers(min_value=0, max_value=4),
    n_without_ref=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100, deadline=None)
def test_p24_records_without_reference_excluded_from_reference_dependent_only(
    n_with_ref, n_without_ref
):
    calls: list = []
    with_ref = [
        {"id": f"with{i}", "question": "q", "answer": "a", "contexts": ["c"], "reference": "gt"}
        for i in range(n_with_ref)
    ]
    without_ref = [
        {"id": f"without{i}", "question": "q", "answer": "a", "contexts": ["c"]}
        for i in range(n_without_ref)
    ]
    samples = with_ref + without_ref

    with _fake_call_ragas(calls):
        framework = RagasEvaluationFramework()
        result = framework.evaluate(samples, metrics=["faithfulness", "context_precision"])

    # Reference-free metric ran over every record.
    ref_free_calls = [c for c in calls if c[1] == ["faithfulness"]]
    assert ref_free_calls
    assert len(ref_free_calls[0][0]) == len(samples)

    # Reference-dependent metric ran only over the with-reference subset.
    ref_dep_calls = [c for c in calls if c[1] == ["context_precision"]]
    if with_ref:
        assert len(ref_dep_calls) == 1
        assert len(ref_dep_calls[0][0]) == n_with_ref
    else:
        assert not ref_dep_calls

    # Every without-reference record id is reported as excluded; with-reference ids are not.
    excluded = set(result.excluded_reference_dependent)
    assert excluded == {s["id"] for s in without_ref}


@given(n=st.integers(min_value=0, max_value=5))
@settings(max_examples=50, deadline=None)
def test_p24_no_reference_dependent_metric_requested_means_no_exclusion_reporting(n):
    calls: list = []
    samples = [{"id": f"s{i}", "question": "q", "answer": "a", "contexts": ["c"]} for i in range(n)]

    with _fake_call_ragas(calls):
        framework = RagasEvaluationFramework()
        result = framework.evaluate(samples, metrics=["faithfulness", "answer_relevancy"])

    assert result.excluded_reference_dependent == []
