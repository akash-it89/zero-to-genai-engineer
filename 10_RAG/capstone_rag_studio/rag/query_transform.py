"""QueryTransformer options: pre-retrieval query rewriting/expansion (Req 16).

``none`` is the identity no-op transform. ``hyde`` asks the variant's GenerationLLM
(via ``ctx.generation_llm``, never imported directly — Req 12.6) to write a
hypothetical answer and embeds that instead of the raw question. ``multi_query``
asks for N paraphrases; the orchestrator retrieves each and merges/dedupes
(Req 16.4, P18) before governance. Reserved slots reject at execution time with a
"reserved extension slot unavailable in v1" error (Req 16.6).
"""
from __future__ import annotations

from rag.interfaces import PipelineContext, QueryPlan, QueryTransformer


class ReservedExtensionSlotError(Exception):
    """Raised when a reserved (not-yet-implemented) extension slot is executed (Req 16.6)."""

    def __init__(self, key: str, target: str):
        self.key = key
        self.target = target
        super().__init__(f"'{key}' is a reserved extension slot unavailable in v1 (target: {target}).")


class NoneQueryTransformer(QueryTransformer):
    """Identity: retrieve using the raw question, unchanged (Req 20.4 no-op guarantee)."""

    def transform(self, question: str, ctx: PipelineContext) -> QueryPlan:
        return QueryPlan(queries=[question], embed_texts=None, merge=False)


class HydeQueryTransformer(QueryTransformer):
    """HyDE: embed a hypothetical answer document instead of the raw question (Req 16.1, 16.2)."""

    def transform(self, question: str, ctx: PipelineContext) -> QueryPlan:
        if ctx.generation_llm is None:
            raise RuntimeError("HyDE requires a configured GenerationLLM on the pipeline context.")
        hypothetical = ctx.generation_llm.generate(
            f"Write a short hypothetical passage that would answer this question: {question}",
            context_chunks=[],
        )
        return QueryPlan(queries=[question], embed_texts=[hypothetical.answer], merge=False)


class MultiQueryTransformer(QueryTransformer):
    """Multi-Query: N paraphrases of the question, to be retrieved and merged (Req 16.3, 16.4)."""

    def __init__(self, n: int = 3):
        self.n = n

    def transform(self, question: str, ctx: PipelineContext) -> QueryPlan:
        if ctx.generation_llm is None:
            raise RuntimeError("Multi-Query requires a configured GenerationLLM on the pipeline context.")
        prompt = (
            f"Generate {self.n} different paraphrases of this question, one per line, "
            f"no numbering: {question}"
        )
        result = ctx.generation_llm.generate(prompt, context_chunks=[])
        paraphrases = [line.strip() for line in result.answer.splitlines() if line.strip()]
        queries = [question, *paraphrases[: self.n]]
        return QueryPlan(queries=queries, embed_texts=None, merge=True)


class ReservedQueryTransformer(QueryTransformer):
    """Placeholder for `query_decomposition`/`self_query` — rejects at execution (Req 16.6)."""

    def __init__(self, key: str):
        self.key = key

    def transform(self, question: str, ctx: PipelineContext) -> QueryPlan:
        raise ReservedExtensionSlotError(self.key, "query_transform")


def make_query_transformer(name: str) -> QueryTransformer:
    """Construct the QueryTransformer registered under ``name`` (Req 1.1, 16)."""
    if name == "none":
        return NoneQueryTransformer()
    if name == "hyde":
        return HydeQueryTransformer()
    if name == "multi_query":
        return MultiQueryTransformer()
    if name in ("query_decomposition", "self_query"):
        return ReservedQueryTransformer(name)
    raise ValueError(f"Unknown query_transform option: '{name}'")
