"""Feature: rag-studio — cross-store integration tests (Req 11.9, 23.4).

Governance is identical across memory/FAISS/Chroma on the same generated corpus, and
a Chroma index survives a simulated backend restart (a brand-new process/object graph
pointed at the same persist directory, per rag.governance's "no in-memory cache
required" contract).
"""
from __future__ import annotations

import shutil
import tempfile

import numpy as np

from rag.governance import GovernanceFilter, InMemoryAccessPolicyProvider
from rag.interfaces import AccessPolicy, Candidate, Chunk, Principal
from rag.stores import ChromaVectorStore, FaissVectorStore, MemoryVectorStore

DIM = 8


def _deterministic_vector(text: str) -> np.ndarray:
    """A cheap, deterministic, dependency-free stand-in for a real embedding —
    consistent hashing of characters into a fixed-size vector."""
    vec = np.zeros(DIM, dtype=np.float32)
    for i, ch in enumerate(text):
        vec[(ord(ch) + i) % DIM] += 1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


CORPUS = [
    Chunk(id="c0", text="Paris is the capital of France.", source="public_doc"),
    Chunk(id="c1", text="Tokyo is the capital of Japan.", source="public_doc"),
    Chunk(id="c2", text="Confidential HR memo about salaries.", source="restricted_doc"),
]
VECTORS = np.stack([_deterministic_vector(c.text) for c in CORPUS])
QUERY_VEC = _deterministic_vector("What is the capital of France?")


def _authorize_and_filter(candidates: list[Candidate], principal: Principal) -> tuple[list[str], int]:
    provider = InMemoryAccessPolicyProvider({
        "public_doc": AccessPolicy(access_level="PUBLIC"),
        "restricted_doc": AccessPolicy(access_level="RESTRICTED", owner="carol", acl=["hr-team"]),
    })
    result = GovernanceFilter(provider).filter(candidates, principal)
    return sorted(c.chunk.id for c in result.authorized), result.filtered_count


def test_governance_identical_across_memory_faiss_chroma():
    alice = Principal(id="alice")
    per_store_results: dict[str, tuple[list[str], int]] = {}

    memory_store = MemoryVectorStore()
    memory_store.add([c.id for c in CORPUS], VECTORS, CORPUS)
    per_store_results["memory"] = _authorize_and_filter(memory_store.search(QUERY_VEC, k=10), alice)

    faiss_store = FaissVectorStore(dim=DIM)
    faiss_store.add([c.id for c in CORPUS], VECTORS, CORPUS)
    per_store_results["faiss"] = _authorize_and_filter(faiss_store.search(QUERY_VEC, k=10), alice)

    tmp = tempfile.mkdtemp()
    try:
        chroma_store = ChromaVectorStore(persist_dir=tmp)
        chroma_store.add([c.id for c in CORPUS], VECTORS, CORPUS)
        per_store_results["chroma"] = _authorize_and_filter(chroma_store.search(QUERY_VEC, k=10), alice)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # Same authorized doc ids, same filtered count, regardless of vector store backend.
    authorized_sets = {store: ids for store, (ids, _count) in per_store_results.items()}
    filtered_counts = {store: count for store, (_ids, count) in per_store_results.items()}

    assert authorized_sets["memory"] == authorized_sets["faiss"] == authorized_sets["chroma"]
    assert authorized_sets["memory"] == ["c0", "c1"]   # restricted c2 excluded for alice
    assert filtered_counts["memory"] == filtered_counts["faiss"] == filtered_counts["chroma"] == 1


def test_chroma_index_persists_across_simulated_restart():
    tmp = tempfile.mkdtemp()
    try:
        # "Session 1": build and populate the index.
        store1 = ChromaVectorStore(persist_dir=tmp)
        store1.add([c.id for c in CORPUS], VECTORS, CORPUS)
        store1.persist()
        del store1   # drop all in-process references — nothing but the disk survives

        # "Session 2" (simulated restart): a brand-new object, no shared in-memory state.
        store2 = ChromaVectorStore(persist_dir=tmp)
        results = store2.search(QUERY_VEC, k=10)

        result_ids = sorted(c.chunk.id for c in results)
        assert result_ids == ["c0", "c1", "c2"]

        # The reconstructed chunks carry real text/source (Req 23.4), not placeholders,
        # so downstream governance/rerank/generation still work after a restart.
        by_id = {c.chunk.id: c.chunk for c in results}
        assert by_id["c0"].text == "Paris is the capital of France."
        assert by_id["c2"].source == "restricted_doc"

        # Governance still filters correctly against the restart-reconstructed chunks.
        alice_ids, filtered_count = _authorize_and_filter(results, Principal(id="alice"))
        assert alice_ids == ["c0", "c1"]
        assert filtered_count == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
