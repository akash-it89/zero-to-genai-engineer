"""Retrieval-stage ablation metrics: R@1, R@3, MRR@10, NDCG@3.

Companion to :mod:`rag.evaluation` (which scores the *generation* stage via RAGAS/
DeepEval): this module scores the *retrieval* stage — did the pipeline find the
right source document, and how highly did it rank it — against a golden set of
``{"question": ..., "expected_sources": [...]}`` items. Metric definitions match
``student_group_datasets/EVALUATION_METHODOLOGY.md`` exactly:

* **R@1 / R@3** — did a chunk from an expected source document appear in the top
  1 / 3 ranked results.
* **MRR@10** — ``1 / rank`` of the first matching chunk within the top 10 (0 if
  none found), rewarding a match at rank 1 over a match at rank 8.
* **NDCG@3** — binary relevance (1 if the chunk's source is in
  ``expected_sources`` else 0) fed through the standard DCG/IDCG formula.

Pure functions only — no provider I/O, no FastAPI/pipeline imports — so this stays
importable and unit-testable in isolation, matching every other module under
``rag/`` (module-isolation convention, see ``rag/interfaces.py``).
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from rag.interfaces import RetrievalMetricScores

METRIC_NAMES = ("r@1", "r@3", "mrr@10", "ndcg@3")


def _matches(ranked_sources: Sequence[str], expected_sources: Sequence[str], limit: Optional[int] = None) -> list[int]:
    """Binary relevance (1/0) for each of the first ``limit`` ranked sources."""
    expected = set(expected_sources)
    window = ranked_sources[:limit] if limit is not None else ranked_sources
    return [1 if source in expected else 0 for source in window]


def recall_at_k(ranked_sources: Sequence[str], expected_sources: Sequence[str], k: int) -> float:
    """1.0 if any of the top-``k`` ranked sources is in ``expected_sources``, else 0.0."""
    if not expected_sources:
        return 0.0
    return 1.0 if any(_matches(ranked_sources, expected_sources, limit=k)) else 0.0


def mrr_at_k(ranked_sources: Sequence[str], expected_sources: Sequence[str], k: int = 10) -> float:
    """``1 / rank`` of the first matching source within the top ``k``; 0.0 if none found."""
    if not expected_sources:
        return 0.0
    expected = set(expected_sources)
    for rank, source in enumerate(ranked_sources[:k], start=1):
        if source in expected:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_sources: Sequence[str], expected_sources: Sequence[str], k: int = 3) -> float:
    """Binary-relevance NDCG@k: ``DCG@k`` (of the actual ranking) / ``IDCG@k`` (best-possible ranking).

    The golden set gives *document*-level ground truth, but retrieval ranks
    *chunks* — several relevant chunks can legitimately come from the same
    expected source document and occupy multiple top-k ranks at once (e.g. all
    top 3 chunks are from the one right document). IDCG therefore assumes every
    one of the ``k`` ranks *could* be relevant (``[1] * k``), not
    ``min(k, len(expected_sources))`` — capping by the count of expected
    *documents* would let two relevant chunks from one document push DCG past
    IDCG and NDCG above 1.0, breaking the metric's [0, 1] guarantee.
    """
    if not expected_sources:
        return 0.0
    relevances = _matches(ranked_sources, expected_sources, limit=k)
    dcg = sum(rel / math.log2(rank + 1) for rank, rel in enumerate(relevances, start=1))

    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, k + 1))

    return dcg / idcg if idcg > 0 else 0.0


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def score_retrieval(
    per_query_ranked: list[list[str]],
    per_query_expected: list[Sequence[str]],
    per_query_type: Optional[list[Optional[str]]] = None,
) -> RetrievalMetricScores:
    """Average R@1/R@3/MRR@10/NDCG@3 across every query, plus a per-``query_type``
    breakdown when ``per_query_type`` entries are supplied (feeds the methodology's
    Stage 5 keyword-vs-semantic-query comparison). Queries whose ``per_query_type``
    entry is ``None`` are included in ``overall`` but excluded from every group in
    ``by_query_type``.

    ``per_query_ranked[i]`` is the ranked list of chunk *source* document ids
    returned for query ``i``; ``per_query_expected[i]`` is that query's set of
    ground-truth source documents.
    """
    n = len(per_query_ranked)
    if n != len(per_query_expected):
        raise ValueError("per_query_ranked and per_query_expected must be the same length.")

    def _score_subset(indices: list[int]) -> dict[str, float]:
        r1 = [recall_at_k(per_query_ranked[i], per_query_expected[i], 1) for i in indices]
        r3 = [recall_at_k(per_query_ranked[i], per_query_expected[i], 3) for i in indices]
        mrr = [mrr_at_k(per_query_ranked[i], per_query_expected[i], 10) for i in indices]
        ndcg = [ndcg_at_k(per_query_ranked[i], per_query_expected[i], 3) for i in indices]
        return {"r@1": _average(r1), "r@3": _average(r3), "mrr@10": _average(mrr), "ndcg@3": _average(ndcg)}

    overall = _score_subset(list(range(n)))

    by_query_type: dict[str, dict[str, float]] = {}
    if per_query_type is not None:
        groups: dict[str, list[int]] = {}
        for i, qtype in enumerate(per_query_type):
            if qtype:
                groups.setdefault(qtype, []).append(i)
        for qtype, indices in groups.items():
            by_query_type[qtype] = _score_subset(indices)

    return RetrievalMetricScores(overall=overall, by_query_type=by_query_type)
