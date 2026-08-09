"""Pipeline configuration — every module's strategy is chosen here.

A ``PipelineConfig`` is one named "strategy variant": every field maps to a
selectable strategy or model discovered through :mod:`rag.registry`. The dataclass
is a plain data holder (no provider imports) so the package stays transport-agnostic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields


@dataclass
class PipelineConfig:
    """A single RAG strategy variant. Every field maps to a selectable strategy/model."""

    name: str = "Default"

    # ingestion / chunking
    chunk_strategy: str = "recursive"   # recursive | token | semantic | markdown
    chunk_size: int = 500
    chunk_overlap: int = 60

    # embeddings + vector store
    embedding: str = "openai-3-small"   # openai-3-small | openai-3-large | bge-small | minilm
    vector_store: str = "memory"        # memory | chroma | faiss | pinecone

    # pre-retrieval  (query transformation)
    query_transform: str = "none"       # none | hyde | multi_query | (reserved: query_decomposition, self_query)

    # retrieval
    retrieval: str = "hybrid_rrf"       # dense | bm25 | hybrid_rrf | hybrid_weighted
    top_k: int = 20                     # first-stage candidates
    alpha: float = 0.5                  # weighted fusion: alpha*dense + (1-alpha)*sparse
    rrf_k: int = 60

    # post-retrieval
    post_retrieval: str = "none"        # none | contextual_compression

    # reranking
    reranker: str = "cross_encoder"     # none | cross_encoder | flashrank | cohere | llm_listwise
    rerank_top_k: int = 5               # final chunks passed to the LLM

    # generation
    llm: str = "gpt-4o-mini"            # gpt-4o-mini | gpt-4o | openrouter:<model>
    temperature: float = 0.0           # default 0.0 for reproducibility (Req 22.2, 23.2)

    # orchestration + cross-cutting
    orchestrator: str = "linear"        # linear | (reserved: crag, self_rag, agentic_rag)
    caching: str = "exact_match"        # exact_match (default on) | semantic | off
    guardrails: str = "light"           # light (default on) | off

    def to_dict(self) -> dict:
        """Serialize for SQLite storage / API responses."""
        return asdict(self)

    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in fields(cls))

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineConfig":
        """Build a config from a dict, dropping unknown keys (backward-compatible)."""
        allowed = set(cls.field_names())
        return cls(**{k: v for k, v in d.items() if k in allowed})

    @classmethod
    def normalize(cls, d: dict) -> "PipelineConfig":
        """Fill every omitted field with its documented default and keep supplied values.

        Unlike :meth:`from_dict`, this is the canonical entry point for UI-submitted
        partial configs: omitted fields receive their documented defaults
        (``query_transform=none``, ``post_retrieval=none``, ``orchestrator=linear``,
        ``caching=exact_match``, ``guardrails=light``, ``temperature=0.0``), and
        unknown keys are ignored. (Req 2.5, 2.7, 22.2)
        """
        return cls.from_dict(dict(d or {}))
