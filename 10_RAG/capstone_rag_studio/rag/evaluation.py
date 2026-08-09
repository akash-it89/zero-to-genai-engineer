"""EvaluationFramework adapters: RAGAS and DeepEval (Req 7, 8).

Both adapters accept the same ``samples`` shape: a list of dicts with ``question``,
``answer``, ``contexts`` (list[str], already governance-authorized — Req 7.1, 8.9),
an optional ``id``, and an optional ``reference`` (ground-truth answer). Reference-
free metrics (``faithfulness``, ``answer_relevancy``) run over every sample.
Reference-dependent metrics (``context_precision``, ``context_recall``, DeepEval's
``geval``) run only over samples carrying a ``reference``; samples lacking one are
excluded from those metrics and reported on ``MetricScores.excluded_reference_dependent``
(Req 8.8), while the reference-free metrics still apply to all records.

The actual RAGAS/DeepEval SDK calls are isolated behind ``_call_ragas``/``_call_deepeval``
so tests can substitute a deterministic mocked judge (provider I/O is mocked in every
property/unit test per project convention) without depending on the real, frequently-
changing SDK surface or making a network call.
"""
from __future__ import annotations

from rag.interfaces import EvaluationFramework, MetricScores

REFERENCE_FREE_METRICS = ("faithfulness", "answer_relevancy")
REFERENCE_DEPENDENT_METRICS = ("context_precision", "context_recall", "geval")

DEEPEVAL_JUDGE_MODEL = "gpt-4o"


class EvaluationError(Exception):
    """Raised when an evaluation run cannot complete; the caller's AnswerResult stays
    intact (Req 8.7) — evaluation failure never mutates or discards a prior answer."""

    def __init__(self, framework: str, message: str):
        self.framework = framework
        super().__init__(f"'{framework}' evaluation failed: {message}")


def _sample_id(sample: dict, index: int) -> str:
    return str(sample.get("id", index))


def _partition_metrics(metrics: list[str]) -> tuple[list[str], list[str]]:
    """Return (reference_dependent, reference_free) subsets of `metrics`, in order."""
    needs_ref = [m for m in metrics if m in REFERENCE_DEPENDENT_METRICS]
    ref_free = [m for m in metrics if m not in REFERENCE_DEPENDENT_METRICS]
    return needs_ref, ref_free


# ---------------------------------------------------------------------------
# RAGAS (Req 7.4-7.7, 8.2-8.4)
# ---------------------------------------------------------------------------

def _ensure_ragas_importable() -> None:
    """Shims a Vertex AI submodule some installed ragas releases import unconditionally
    at module load time even though this project never uses Vertex AI. Newer
    `langchain-community` releases dropped that bundled integration, which otherwise
    makes ``import ragas`` crash with ``ModuleNotFoundError`` regardless of provider
    choice. The shim is a no-op stand-in — it is never actually invoked."""
    import sys
    import types

    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    try:
        import langchain_community.chat_models.vertexai  # noqa: F401
        return   # already importable — no shim needed
    except ModuleNotFoundError:
        pass

    shim = types.ModuleType(module_name)

    class ChatVertexAI:  # pragma: no cover - never called, import-compatibility only
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Vertex AI is not used by this project; this is an import shim.")

    shim.ChatVertexAI = ChatVertexAI
    sys.modules[module_name] = shim


def _call_ragas(samples: list[dict], metrics: list[str]) -> dict[str, list[float]]:
    """Runs the real RAGAS evaluation and returns per-sample scores by metric name."""
    _ensure_ragas_importable()
    from datasets import Dataset
    from langchain_openai import OpenAIEmbeddings
    from ragas import evaluate as ragas_evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    metric_objs_by_name = {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
    }
    metric_objs = [metric_objs_by_name[m] for m in metrics if m in metric_objs_by_name]

    rows = []
    for s in samples:
        row = {"question": s["question"], "answer": s["answer"], "contexts": list(s["contexts"])}
        if s.get("reference"):
            row["ground_truth"] = s["reference"]
        rows.append(row)

    try:
        dataset = Dataset.from_list(rows)
        # An explicit embeddings wrapper avoids a bug in ragas 0.4.x's auto-constructed
        # default (a bare `OpenAIEmbeddings` lacking the `.embed_query` ragas expects),
        # which otherwise makes `answer_relevancy` fail on every sample.
        embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))
        result = ragas_evaluate(dataset, metrics=metric_objs, embeddings=embeddings)
        df = result.to_pandas()
    except Exception as exc:
        raise EvaluationError("ragas", str(exc)) from exc

    return {m: df[m].tolist() for m in metrics if m in df.columns}


class RagasEvaluationFramework(EvaluationFramework):
    """RAGAS adapter: faithfulness, answer relevancy (reference-free) and context
    precision/recall (reference-dependent) (Req 7.1, 7.4-7.7, 8.2-8.4, 8.8, 8.9)."""

    def evaluate(self, samples: list[dict], metrics: list[str], reference: bool = False) -> MetricScores:
        result = MetricScores()
        needs_ref, ref_free = _partition_metrics(metrics)

        if ref_free:
            scores = _call_ragas(samples, ref_free)
            for name, values in scores.items():
                if values:
                    result.scores[name] = sum(values) / len(values)

        if needs_ref:
            with_ref = [s for s in samples if s.get("reference")]
            excluded_ids = [_sample_id(s, i) for i, s in enumerate(samples) if not s.get("reference")]
            if with_ref:
                scores = _call_ragas(with_ref, needs_ref)
                for name, values in scores.items():
                    if values:
                        result.scores[name] = sum(values) / len(values)
            result.excluded_reference_dependent = excluded_ids

        return result


# ---------------------------------------------------------------------------
# DeepEval (Req 7.4-7.7, 8.2-8.4, 8.7)
# ---------------------------------------------------------------------------

def _deepeval_metric_for(name: str):
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
        GEval,
    )

    if name == "faithfulness":
        return FaithfulnessMetric(model=DEEPEVAL_JUDGE_MODEL, async_mode=False)
    if name == "answer_relevancy":
        return AnswerRelevancyMetric(model=DEEPEVAL_JUDGE_MODEL, async_mode=False)
    if name == "context_precision":
        return ContextualPrecisionMetric(model=DEEPEVAL_JUDGE_MODEL, async_mode=False)
    if name == "context_recall":
        return ContextualRecallMetric(model=DEEPEVAL_JUDGE_MODEL, async_mode=False)
    if name == "geval":
        return GEval(
            name="Correctness",
            criteria="Determine whether the actual output is factually correct given the expected output.",
            evaluation_params=["input", "actual_output", "expected_output"],
            model=DEEPEVAL_JUDGE_MODEL,
            async_mode=False,
        )
    raise ValueError(f"Unknown DeepEval metric: '{name}'")


def _call_deepeval(
    samples: list[dict], metrics: list[str]
) -> tuple[dict[str, list[float]], dict[str, list[bool]], dict[str, list[str]]]:
    """Runs the real DeepEval judge (gpt-4o, async_mode=False) per sample per metric."""
    import os

    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")  # telemetry opt-out (Req 8.3)

    from deepeval.test_case import LLMTestCase

    metric_objs = {name: _deepeval_metric_for(name) for name in metrics}
    scores: dict[str, list[float]] = {name: [] for name in metrics}
    passed: dict[str, list[bool]] = {name: [] for name in metrics}
    reasons: dict[str, list[str]] = {name: [] for name in metrics}

    for s in samples:
        test_case = LLMTestCase(
            input=s["question"],
            actual_output=s["answer"],
            retrieval_context=list(s["contexts"]),
            expected_output=s.get("reference"),
        )
        for name, metric in metric_objs.items():
            try:
                metric.measure(test_case)
            except Exception as exc:
                raise EvaluationError("deepeval", str(exc)) from exc
            scores[name].append(float(metric.score))
            passed[name].append(bool(metric.is_successful()))
            reasons[name].append(getattr(metric, "reason", "") or "")
    return scores, passed, reasons


class DeepEvalEvaluationFramework(EvaluationFramework):
    """DeepEval adapter: same metric families as RAGAS plus GEval, gpt-4o judge,
    synchronous (async_mode=False), telemetry opted out (Req 7.4-7.7, 8.2-8.4)."""

    def evaluate(self, samples: list[dict], metrics: list[str], reference: bool = False) -> MetricScores:
        result = MetricScores()
        needs_ref, ref_free = _partition_metrics(metrics)

        def _run(subset: list[dict], metric_names: list[str]) -> None:
            if not subset or not metric_names:
                return
            scores, passed, reasons = _call_deepeval(subset, metric_names)
            for name in metric_names:
                values = scores.get(name, [])
                if values:
                    result.scores[name] = sum(values) / len(values)
                sample_passed = passed.get(name, [])
                result.passed[name] = all(sample_passed) if sample_passed else False
                failing_reasons = [
                    r for r, p in zip(reasons.get(name, []), sample_passed) if not p and r
                ]
                result.reasons[name] = "; ".join(failing_reasons) if failing_reasons else "all samples passed"

        _run(samples, ref_free)

        if needs_ref:
            with_ref = [s for s in samples if s.get("reference")]
            excluded_ids = [_sample_id(s, i) for i, s in enumerate(samples) if not s.get("reference")]
            _run(with_ref, needs_ref)
            result.excluded_reference_dependent = excluded_ids

        return result


def make_evaluation_framework(name: str) -> EvaluationFramework:
    """Construct the EvaluationFramework registered under ``name`` (Req 1.1, 7, 8)."""
    if name == "ragas":
        return RagasEvaluationFramework()
    if name == "deepeval":
        return DeepEvalEvaluationFramework()
    raise ValueError(f"Unknown evaluation option: '{name}'")
