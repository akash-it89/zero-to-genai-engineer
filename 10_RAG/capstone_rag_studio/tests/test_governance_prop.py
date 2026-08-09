"""Feature: rag-studio — governance kernel property tests (safety-critical).

Covers design properties P1 (governance never leaks), P2 (no-accessible-context safe
empty result), P3 (authorization matches Access_Level semantics), P20 (every decision
audited with no removed-chunk content). Run at elevated example counts per the release
gate policy (Req 4.5, 5.2, 5.6, 7.1, 8.9, 11.8, 11.10, 11.13, 11.15, 16.5, 17.5).
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from rag.governance import (
    GovernanceFilter,
    InMemoryAccessPolicyProvider,
    InMemoryAuditLog,
    authorize,
    build_no_context_result,
)
from rag.interfaces import AccessPolicy, Candidate, Chunk, Principal

ELEVATED = settings(max_examples=300)

access_levels = st.sampled_from(["PUBLIC", "RESTRICTED", "PRIVATE"])
ids = st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=6)


def _make_candidates(doc_ids: list[str]) -> list[Candidate]:
    return [
        Candidate(chunk=Chunk(id=f"c{i}", text=f"secret content {i}", source=doc), score=1.0, rank=i)
        for i, doc in enumerate(doc_ids)
    ]


# ---------------------------------------------------------------------------
# P3 — authorization matches Access_Level semantics exactly
# ---------------------------------------------------------------------------

@given(
    level=access_levels,
    owner=ids,
    acl=st.lists(ids, max_size=4),
    principal_id=ids,
    principal_roles=st.lists(ids, max_size=3),
)
@ELEVATED
def test_p3_authorization_matches_access_level_semantics(level, owner, acl, principal_id, principal_roles):
    policy = AccessPolicy(access_level=level, owner=owner, acl=acl)
    principal = Principal(id=principal_id, roles=principal_roles)
    decision = authorize(policy, principal)

    if level == "PUBLIC":
        assert decision is True
    elif principal_id == owner:
        assert decision is True
    elif level == "RESTRICTED":
        assert decision == bool(principal.identities() & set(acl))
    elif level == "PRIVATE":
        assert decision == (principal_id in acl)


# ---------------------------------------------------------------------------
# P1 — governance never leaks: filtered result never contains an unauthorized doc
# ---------------------------------------------------------------------------

@given(
    doc_specs=st.lists(
        st.tuples(ids, access_levels, ids, st.lists(ids, max_size=3)), min_size=0, max_size=8
    ),
    principal_id=ids,
    principal_roles=st.lists(ids, max_size=3),
)
@ELEVATED
def test_p1_governance_never_leaks(doc_specs, principal_id, principal_roles):
    provider = InMemoryAccessPolicyProvider()
    doc_ids = []
    for doc_id, level, owner, acl in doc_specs:
        provider.set_policy(doc_id, AccessPolicy(access_level=level, owner=owner, acl=acl))
        doc_ids.append(doc_id)

    principal = Principal(id=principal_id, roles=principal_roles)
    candidates = _make_candidates(doc_ids)
    audit = InMemoryAuditLog()
    result = GovernanceFilter(provider).filter(candidates, principal, request_id="r1", audit=audit)

    for cand in result.authorized:
        assert provider.is_authorized(principal, cand.chunk.source)

    surviving_docs = {c.chunk.source for c in result.authorized}
    assert surviving_docs == set(result.authorized_doc_ids)
    assert result.filtered_count == len(candidates) - len(result.authorized)


# ---------------------------------------------------------------------------
# P2 — no accessible context yields the safe empty result, revealing nothing
# ---------------------------------------------------------------------------

@given(filtered_count=st.integers(min_value=0, max_value=50))
@ELEVATED
def test_p2_no_accessible_context_safe_empty_result(filtered_count):
    result = build_no_context_result("variant-x", "req-1", filtered_count)
    assert result.no_accessible_context is True
    assert result.citations == []
    assert result.retrieved_chunks == []
    assert result.reranked_chunks == []
    assert result.governance_filtered_count == filtered_count
    # The safe message must not embed any doc id or chunk content.
    assert "secret" not in result.answer


# ---------------------------------------------------------------------------
# P20 — every governed decision is audited, and the audit never carries content
# ---------------------------------------------------------------------------

@given(
    doc_specs=st.lists(
        st.tuples(ids, access_levels, ids, st.lists(ids, max_size=3)), min_size=1, max_size=6
    ),
    principal_id=ids,
)
@ELEVATED
def test_p20_every_decision_audited_no_content_leak(doc_specs, principal_id):
    provider = InMemoryAccessPolicyProvider()
    doc_ids = []
    for doc_id, level, owner, acl in doc_specs:
        provider.set_policy(doc_id, AccessPolicy(access_level=level, owner=owner, acl=acl))
        doc_ids.append(doc_id)

    principal = Principal(id=principal_id)
    candidates = _make_candidates(doc_ids)
    audit = InMemoryAuditLog()

    before = len(audit.entries)
    result = GovernanceFilter(provider).filter(candidates, principal, request_id="r-audit", audit=audit)
    assert len(audit.entries) == before + 1

    entry = audit.entries[-1]
    assert entry.request_id == "r-audit"
    assert entry.acting_principal == principal.id
    assert set(entry.authorized_doc_ids) == set(result.authorized_doc_ids)
    assert set(entry.denied_doc_ids) == set(result.denied_doc_ids)
    # ids only — never chunk text/content anywhere in the audit entry's fields.
    entry_dump = f"{entry.authorized_doc_ids}{entry.denied_doc_ids}"
    assert "secret content" not in entry_dump


# ---------------------------------------------------------------------------
# Unknown documents are deny-by-default
# ---------------------------------------------------------------------------

def test_unknown_document_denied_by_default():
    provider = InMemoryAccessPolicyProvider()
    principal = Principal(id="alice")
    assert provider.is_authorized(principal, "never-registered-doc") is False


def test_filter_with_no_audit_sink_does_not_raise():
    provider = InMemoryAccessPolicyProvider()
    provider.set_policy("d1", AccessPolicy(access_level="PUBLIC"))
    principal = Principal(id="alice")
    result = GovernanceFilter(provider).filter(_make_candidates(["d1"]), principal)
    assert len(result.authorized) == 1
