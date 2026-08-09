"""Governance kernel: access-policy authorization + retrieval-time filtering + audit.

This is the safety-critical heart of RAG Studio. The ``Governance_Filter`` runs after
retrieval and before every downstream stage, so post-retrieval, reranking, generation,
citation, evaluation, and cache storage only ever see authorized chunks (Req 11.8-11.10).
Authorization semantics follow the Access_Level rules exactly (Req 11.3-11.6). Every
governed request appends exactly one append-only Audit_Log entry recording the partition
of document ids — never any removed chunk's content (Req 11.13, 11.14).

Imports only :mod:`rag.interfaces` (module isolation, Req 12.6).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rag.interfaces import (
    AccessPolicy,
    AccessPolicyProvider,
    AnswerResult,
    Candidate,
    Principal,
)


# ---------------------------------------------------------------------------
# Authorization semantics (Req 11.3-11.6) — pure function
# ---------------------------------------------------------------------------

def authorize(policy: AccessPolicy, principal: Principal) -> bool:
    """Return the Authorization_Decision for one policy + principal.

    * PUBLIC    -> authorized for every principal.
    * RESTRICTED-> owner, or a User/Role/Group named in the ACL.
    * PRIVATE   -> owner, or the principal explicitly named (by id) in the ACL.
    """
    level = policy.access_level
    if level == "PUBLIC":
        return True
    if principal.id and principal.id == policy.owner:
        return True
    acl = set(policy.acl)
    if level == "RESTRICTED":
        return bool(principal.identities() & acl)   # id OR any role/group
    if level == "PRIVATE":
        return principal.id in acl                  # explicit id only
    return False                                    # unknown level -> deny


# ---------------------------------------------------------------------------
# Access-policy provider (Req 11.16) — demo in-memory implementation
# ---------------------------------------------------------------------------

class InMemoryAccessPolicyProvider(AccessPolicyProvider):
    """Stores Access_Policies in memory and answers authorization decisions.

    Registered in the Registry behind the ``AccessPolicyProvider`` interface so it can be
    swapped for an external provider without touching other modules (Req 11.16).
    """

    def __init__(self, policies: dict[str, AccessPolicy] | None = None):
        self._policies: dict[str, AccessPolicy] = dict(policies or {})

    def get_policy(self, doc_id: str) -> AccessPolicy:
        # Unknown documents are treated as maximally restricted (deny-by-default).
        return self._policies.get(doc_id, AccessPolicy(access_level="PRIVATE", owner="\x00unknown", acl=[]))

    def set_policy(self, doc_id: str, policy: AccessPolicy) -> None:
        self._policies[doc_id] = policy

    def is_authorized(self, principal: Principal, doc_id: str) -> bool:
        if doc_id not in self._policies:
            return False                            # unknown doc -> deny
        return authorize(self._policies[doc_id], principal)


# ---------------------------------------------------------------------------
# Audit log (Req 11.13)
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    request_id: str
    acting_principal: str
    authorized_doc_ids: list[str]
    denied_doc_ids: list[str]
    # NOTE: ids only — never chunk content (Req 11.14)


class AuditSink:
    """Append-only audit interface. The SQLite-backed sink lives in persistence."""

    def append(self, entry: AuditEntry) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryAuditLog(AuditSink):
    def __init__(self):
        self.entries: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


# ---------------------------------------------------------------------------
# Governance filter (Req 11.8-11.10, 11.14)
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    authorized: list[Candidate] = field(default_factory=list)
    filtered_count: int = 0                        # count only (Req 11.14)
    authorized_doc_ids: list[str] = field(default_factory=list)
    denied_doc_ids: list[str] = field(default_factory=list)


class GovernanceFilter:
    """Removes candidates the Acting_Principal is not authorized to access.

    Runs identically for every retrieval mode and vector store (Req 11.9). Writes exactly
    one Audit_Log entry per governed request when an audit sink is provided (Req 11.13).
    """

    def __init__(self, provider: AccessPolicyProvider):
        self.provider = provider

    def filter(
        self,
        candidates: list[Candidate],
        principal: Principal,
        request_id: str = "",
        audit: AuditSink | None = None,
    ) -> FilterResult:
        authorized: list[Candidate] = []
        authorized_ids: set[str] = set()
        denied_ids: set[str] = set()
        for cand in candidates:
            doc = cand.chunk.source
            if self.provider.is_authorized(principal, doc):
                authorized.append(cand)
                authorized_ids.add(doc)
            else:
                denied_ids.add(doc)
        result = FilterResult(
            authorized=authorized,
            filtered_count=len(candidates) - len(authorized),
            authorized_doc_ids=sorted(authorized_ids),
            denied_doc_ids=sorted(denied_ids),
        )
        if audit is not None:
            audit.append(AuditEntry(
                request_id=request_id,
                acting_principal=principal.id,
                authorized_doc_ids=result.authorized_doc_ids,
                denied_doc_ids=result.denied_doc_ids,
            ))
        return result


# ---------------------------------------------------------------------------
# No-accessible-context result (Req 11.15)
# ---------------------------------------------------------------------------

NO_CONTEXT_MESSAGE = "No accessible context was found for your question."


def build_no_context_result(variant_name: str, request_id: str, filtered_count: int) -> AnswerResult:
    """Safe empty result revealing nothing about restricted content (Req 11.15)."""
    return AnswerResult(
        variant_name=variant_name,
        answer=NO_CONTEXT_MESSAGE,
        citations=[],
        retrieved_chunks=[],
        reranked_chunks=[],
        governance_filtered_count=filtered_count,
        trace_id=request_id,
        no_accessible_context=True,
    )
