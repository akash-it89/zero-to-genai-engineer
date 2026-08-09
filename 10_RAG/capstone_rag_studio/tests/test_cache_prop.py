"""Feature: rag-studio — cache property tests (safety-critical, Req 18).

Covers design property P10: cache is principal-and-config scoped; disabled means no
read/write happens at all; a miss stores the result and a subsequent hit returns the
stored value exactly. Run at an elevated example count per the release-gate policy
(Req 11.14, 18.2, 18.3, 18.4, 18.5, 18.6, 19.6, 24.1, 24.2, 24.3, 24.5).
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from rag.cache import ExactMatchCache, OffCache
from rag.interfaces import AnswerResult, Principal

ELEVATED = settings(max_examples=300)

ids = st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=8)
questions = st.text(min_size=1, max_size=40)
configs = st.dictionaries(ids, st.one_of(st.text(max_size=10), st.integers(), st.floats(allow_nan=False)), max_size=4)


def _result(answer: str) -> AnswerResult:
    return AnswerResult(variant_name="v1", answer=answer)


# ---------------------------------------------------------------------------
# P10a — exact-match: miss stores, hit returns stored, scoped by principal+config
# ---------------------------------------------------------------------------

@given(
    principal_id=ids,
    config=configs,
    question=questions,
    answer=st.text(min_size=0, max_size=40),
)
@ELEVATED
def test_p10_exact_match_miss_then_hit(principal_id, config, question, answer):
    cache = ExactMatchCache()
    principal = Principal(id=principal_id)
    key = cache.key(principal, config, question)

    # Miss before any write.
    assert cache.get(key) is None

    stored = _result(answer)
    cache.put(key, stored)

    # Hit returns exactly the stored value.
    assert cache.get(key) is stored


@given(
    principal_a=ids, principal_b=ids,
    config=configs,
    question=questions,
)
@ELEVATED
def test_p10_exact_match_scoped_by_principal(principal_a, principal_b, config, question):
    if principal_a == principal_b:
        return
    cache = ExactMatchCache()
    key_a = cache.key(Principal(id=principal_a), config, question)
    key_b = cache.key(Principal(id=principal_b), config, question)

    cache.put(key_a, _result("answer for a"))

    # A different principal never sees another principal's cached entry (same config+question).
    assert cache.get(key_b) is None
    assert key_a != key_b


@given(
    principal_id=ids,
    config_a=configs, config_b=configs,
    question=questions,
)
@ELEVATED
def test_p10_exact_match_scoped_by_config(principal_id, config_a, config_b, question):
    if config_a == config_b:
        return
    cache = ExactMatchCache()
    principal = Principal(id=principal_id)
    key_a = cache.key(principal, config_a, question)
    key_b = cache.key(principal, config_b, question)

    cache.put(key_a, _result("answer for config a"))

    # A different config is a distinct scope even for the same principal+question.
    assert cache.get(key_b) is None
    assert key_a != key_b


@given(principal_id=ids, config=configs, question_a=questions, question_b=questions)
@ELEVATED
def test_p10_exact_match_scoped_by_question(principal_id, config, question_a, question_b):
    if question_a == question_b:
        return
    cache = ExactMatchCache()
    principal = Principal(id=principal_id)
    key_a = cache.key(principal, config, question_a)
    key_b = cache.key(principal, config, question_b)

    cache.put(key_a, _result("answer a"))

    assert cache.get(key_b) is None
    assert key_a != key_b


# ---------------------------------------------------------------------------
# P10b — disabled cache: no read or write ever happens
# ---------------------------------------------------------------------------

@given(principal_id=ids, config=configs, question=questions, answer=st.text(max_size=20))
@ELEVATED
def test_p10_off_cache_never_reads_or_writes(principal_id, config, question, answer):
    cache = OffCache()
    principal = Principal(id=principal_id)
    key = cache.key(principal, config, question)

    assert cache.get(key) is None
    cache.put(key, _result(answer))
    # Still a miss after "writing" — disabled means the write never actually happened.
    assert cache.get(key) is None
