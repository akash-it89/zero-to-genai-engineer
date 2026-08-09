"""Feature: rag-studio — retrieval ablation metrics unit tests (R@1/R@3/MRR@10/NDCG@3).

Covers: each metric's core definition per EVALUATION_METHODOLOGY.md, edge cases (no
match, empty expected set, match at the very end of the window), and
`score_retrieval`'s averaging + query-type breakdown behavior.
"""
from __future__ import annotations

import pytest

from rag.interfaces import RetrievalMetricScores
from rag.retrieval_metrics import mrr_at_k, ndcg_at_k, recall_at_k, score_retrieval


# --- recall_at_k ---------------------------------------------------------------

def test_recall_at_k_true_when_expected_source_within_window():
    assert recall_at_k(["a", "b", "c"], ["b"], k=3) == 1.0


def test_recall_at_k_false_when_expected_source_outside_window():
    assert recall_at_k(["a", "b", "c"], ["b"], k=1) == 0.0


def test_recall_at_k_false_when_no_match_at_all():
    assert recall_at_k(["a", "b", "c"], ["z"], k=3) == 0.0


def test_recall_at_k_zero_when_expected_sources_empty():
    assert recall_at_k(["a", "b", "c"], [], k=3) == 0.0


# --- mrr_at_k --------------------------------------------------------------------

def test_mrr_at_k_full_score_when_match_at_rank_one():
    assert mrr_at_k(["a", "b", "c"], ["a"], k=10) == 1.0


def test_mrr_at_k_reciprocal_of_rank_when_match_later():
    assert mrr_at_k(["a", "b", "c"], ["c"], k=10) == pytest.approx(1 / 3)


def test_mrr_at_k_zero_when_match_beyond_k():
    assert mrr_at_k(["a", "b", "c", "d"], ["d"], k=2) == 0.0


def test_mrr_at_k_zero_when_expected_sources_empty():
    assert mrr_at_k(["a", "b"], [], k=10) == 0.0


# --- ndcg_at_k -------------------------------------------------------------------

def test_ndcg_at_k_one_when_every_rank_is_relevant():
    # Every one of the top-k ranks is relevant — matches the ideal ranking exactly.
    assert ndcg_at_k(["a", "b", "c"], ["a", "b", "c"], k=3) == pytest.approx(1.0)


def test_ndcg_at_k_never_exceeds_one_when_multiple_chunks_share_one_expected_source():
    # Regression: two relevant *chunks* from the same expected *document* filling
    # the top-k must not push NDCG above 1.0 (a document-level golden label can't
    # be treated as "only one relevant chunk exists").
    assert ndcg_at_k(["a", "a", "a"], ["a"], k=3) == pytest.approx(1.0)
    assert ndcg_at_k(["a", "a", "x"], ["a"], k=3) <= 1.0


def test_ndcg_at_k_zero_when_nothing_relevant_retrieved():
    assert ndcg_at_k(["a", "b", "c"], ["z"], k=3) == 0.0


def test_ndcg_at_k_penalizes_relevant_result_ranked_lower():
    # Relevant doc at rank 3 scores lower than the same doc at rank 1 (test_ndcg_at_k_one_when_ranking_is_ideal).
    score = ndcg_at_k(["x", "y", "a"], ["a"], k=3)
    assert 0.0 < score < 1.0


def test_ndcg_at_k_zero_when_expected_sources_empty():
    assert ndcg_at_k(["a", "b", "c"], [], k=3) == 0.0


# --- score_retrieval ---------------------------------------------------------------

def test_score_retrieval_averages_across_queries():
    # Query 0: perfect match at rank 1. Query 1: no match at all.
    ranked = [["a", "x", "y"], ["p", "q", "r"]]
    expected = [["a"], ["z"]]
    result = score_retrieval(ranked, expected)
    assert isinstance(result, RetrievalMetricScores)
    assert result.overall["r@1"] == pytest.approx(0.5)   # 1.0 then 0.0, averaged
    assert result.overall["mrr@10"] == pytest.approx(0.5)


def test_score_retrieval_breaks_out_by_query_type():
    ranked = [["a", "x"], ["p", "z"]]
    expected = [["a"], ["z"]]
    query_types = ["keyword", "semantic"]
    result = score_retrieval(ranked, expected, query_types)
    assert result.by_query_type["keyword"]["r@1"] == pytest.approx(1.0)
    assert result.by_query_type["semantic"]["r@1"] == pytest.approx(0.0)


def test_score_retrieval_excludes_none_query_type_from_breakdown_but_keeps_in_overall():
    ranked = [["a"], ["b"]]
    expected = [["a"], ["b"]]
    query_types = ["keyword", None]
    result = score_retrieval(ranked, expected, query_types)
    assert "keyword" in result.by_query_type
    assert len(result.by_query_type) == 1
    assert result.overall["r@1"] == pytest.approx(1.0)   # both queries matched, still counted overall


def test_score_retrieval_empty_golden_set_returns_zeros_not_a_crash():
    result = score_retrieval([], [])
    assert result.overall["r@1"] == 0.0
    assert result.by_query_type == {}


def test_score_retrieval_raises_on_mismatched_lengths():
    with pytest.raises(ValueError):
        score_retrieval([["a"]], [["a"], ["b"]])
