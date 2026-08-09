"""PostRetrievalProcessor options: run after governance, before rerank/generation (Req 17).

Only ever *removes* content — never fabricates or rewrites text (Req 17.3) — and
bounds the returned token count (Req 17.4). Operates only on the governance-authorized
chunk list handed to it by the orchestrator (Req 17.8); it never sees anything the
Governance_Filter already dropped.
"""
from __future__ import annotations

from rag.interfaces import Chunk, PipelineContext, PostRetrievalProcessor, source_prefixed_text


def _approx_token_count(text: str) -> int:
    # Cheap, dependency-free approximation (~4 chars/token) — good enough for a bound.
    return max(1, len(text) // 4)


class NonePostRetrievalProcessor(PostRetrievalProcessor):
    """Identity: returns the authorized chunks unchanged (Req 20.4 no-op guarantee)."""

    def process(self, question: str, chunks: list[Chunk], ctx: PipelineContext) -> list[Chunk]:
        return list(chunks)


class ContextualCompressionProcessor(PostRetrievalProcessor):
    """Removes low-relevance spans/chunks; never invents text; caps total tokens (Req 17.1-17.4, 17.6, 17.7).

    Uses embedding similarity against the question as the relevance signal (local,
    free) rather than an LLM rewrite, so it can only ever drop chunks — it has no
    mechanism to alter the surviving text.
    """

    def __init__(self, relevance_floor: float = 0.15, max_tokens: int = 2000):
        self.relevance_floor = relevance_floor
        self.max_tokens = max_tokens

    def process(self, question: str, chunks: list[Chunk], ctx: PipelineContext) -> list[Chunk]:
        if not chunks:
            return []
        if ctx.embedder is None:
            return list(chunks)   # nothing to score against — pass through unchanged

        query_vec = ctx.embedder.embed_query(question)
        doc_vecs = ctx.embedder.embed_documents([source_prefixed_text(c) for c in chunks])

        import numpy as np

        q = np.asarray(query_vec, dtype=float)
        q_norm = np.linalg.norm(q) or 1.0
        scored: list[tuple[float, Chunk]] = []
        for vec, chunk in zip(doc_vecs, chunks):
            v = np.asarray(vec, dtype=float)
            v_norm = np.linalg.norm(v) or 1.0
            sim = float((q @ v) / (q_norm * v_norm))
            scored.append((sim, chunk))

        # Keep only chunks at/above the relevance floor, most-relevant first.
        scored.sort(key=lambda sv: -sv[0])
        kept: list[Chunk] = []
        total_tokens = 0
        for sim, chunk in scored:
            if sim < self.relevance_floor:
                continue
            tokens = _approx_token_count(chunk.text)
            if kept and total_tokens + tokens > self.max_tokens:
                break   # bound total token count (Req 17.4); always keep at least one
            kept.append(chunk)
            total_tokens += tokens
        return kept or [scored[0][1]]   # never return empty if there was at least one chunk


def make_post_retrieval_processor(name: str) -> PostRetrievalProcessor:
    """Construct the PostRetrievalProcessor registered under ``name`` (Req 1.1, 17)."""
    if name == "none":
        return NonePostRetrievalProcessor()
    if name == "contextual_compression":
        return ContextualCompressionProcessor()
    raise ValueError(f"Unknown post_retrieval option: '{name}'")
