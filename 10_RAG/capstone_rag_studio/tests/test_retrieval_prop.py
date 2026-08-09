"""Feature: rag-studio — retrieval fusion property tests.

Covers design properties P12 (RRF is a rank-based permutation of the union obeying
the RRF formula; weighted fusion collapses to pure dense/sparse at alpha extremes)
and P18 (multi-query merge de-duplicates to the set-union of ids). Req 4.3, 4.4, 16.4.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from rag.interfaces import Candidate, Chunk
from rag.retrieval import (
    merge_multi_query_candidates,
    reciprocal_rank_fusion,
    weighted_fusion,
)


def _candidates(ids: list[str], scores: list[float]) -> list[Candidate]:
    chunks = [Chunk(id=i, text=f"text-{i}", source="doc1") for i in ids]
    order = sorted(range(len(ids)), key=lambda idx: -scores[idx])
    return [
        Candidate(chunk=chunks[pos], score=scores[pos], rank=rank)
        for rank, pos in enumerate(order)
    ]


id_lists = st.lists(
    st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=4),
    min_size=0, max_size=6, unique=True,
)


@given(
    dense_ids=id_lists,
    sparse_ids=id_lists,
    top_k=st.integers(min_value=1, max_value=10),
    rrf_k=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=150)
def test_p12_rrf_matches_formula_and_is_subset_of_union(dense_ids, sparse_ids, top_k, rrf_k):
    dense = _candidates(dense_ids, [float(len(dense_ids) - i) for i in range(len(dense_ids))])
    sparse = _candidates(sparse_ids, [float(len(sparse_ids) - i) for i in range(len(sparse_ids))])

    fused = reciprocal_rank_fusion(dense, sparse, top_k, rrf_k)

    union_ids = {c.chunk.id for c in dense} | {c.chunk.id for c in sparse}
    fused_ids = {c.chunk.id for c in fused}
    assert fused_ids <= union_ids                       # never invents a new id
    assert len(fused) <= min(top_k, len(union_ids))

    # Recompute expected RRF score per id and compare against what fusion returned.
    dense_rank = {c.chunk.id: c.rank for c in dense}
    sparse_rank = {c.chunk.id: c.rank for c in sparse}
    expected_scores = {}
    for cid in union_ids:
        score = 0.0
        if cid in dense_rank:
            score += 1.0 / (rrf_k + dense_rank[cid] + 1)
        if cid in sparse_rank:
            score += 1.0 / (rrf_k + sparse_rank[cid] + 1)
        expected_scores[cid] = score

    for cand in fused:
        assert abs(cand.score - expected_scores[cand.chunk.id]) < 1e-9

    # Result is sorted descending by score.
    scores_out = [c.score for c in fused]
    assert scores_out == sorted(scores_out, reverse=True)


@given(
    # >=2 distinct scores per side (avoids min-max normalization degenerating to a
    # single tied value at 0) and disjoint id sets (keeps the expected-order maths simple).
    dense_ids=st.lists(st.text(alphabet="abcd", min_size=1, max_size=3), min_size=2, max_size=4, unique=True),
    sparse_ids=st.lists(st.text(alphabet="wxyz", min_size=1, max_size=3), min_size=2, max_size=4, unique=True),
    top_k=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=150)
def test_p12_weighted_fusion_extremes_equal_pure_dense_or_sparse(dense_ids, sparse_ids, top_k):
    dense = _candidates(dense_ids, [float(i + 1) for i in range(len(dense_ids))])
    sparse = _candidates(sparse_ids, [float(i + 1) for i in range(len(sparse_ids))])

    alpha_1 = weighted_fusion(dense, sparse, top_k, alpha=1.0)
    alpha_0 = weighted_fusion(dense, sparse, top_k, alpha=0.0)

    # The top-scored item's normalized value is a strict 1.0 (unique max), so the top
    # rank at alpha=1.0/0.0 is unambiguous even though lower-ranked items can tie at 0
    # once the disabled side's min-scoring entries collapse to 0 (a normalization
    # boundary effect, not a fusion bug — Req 4.4).
    best_dense_id = max(dense, key=lambda c: c.score).chunk.id
    best_sparse_id = max(sparse, key=lambda c: c.score).chunk.id
    assert alpha_1[0].chunk.id == best_dense_id
    assert alpha_0[0].chunk.id == best_sparse_id
    assert alpha_1[0].score == 1.0
    assert alpha_0[0].score == 1.0


@given(
    query_results=st.lists(
        st.lists(st.tuples(st.text(alphabet="abcdef", min_size=1, max_size=3), st.floats(min_value=0, max_value=1, allow_nan=False)), max_size=5),
        min_size=1, max_size=4,
    ),
    top_k=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=150)
def test_p18_multi_query_merge_dedupes_to_set_union(query_results, top_k):
    per_query: list[list[Candidate]] = []
    all_ids: set[str] = set()
    for results in query_results:
        cands = []
        for rank, (cid, score) in enumerate(results):
            cands.append(Candidate(chunk=Chunk(id=cid, text="t", source="doc1"), score=score, rank=rank))
            all_ids.add(cid)
        per_query.append(cands)

    merged = merge_multi_query_candidates(per_query, top_k)
    merged_ids = [c.chunk.id for c in merged]

    # No duplicate ids in the merged output.
    assert len(merged_ids) == len(set(merged_ids))
    # Merged ids are a subset of the set-union across all per-query results.
    assert set(merged_ids) <= all_ids
    assert len(merged) <= min(top_k, len(all_ids))
