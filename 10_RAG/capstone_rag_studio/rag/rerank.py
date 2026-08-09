"""Reranker options: reorder governance-filtered candidates (Req 4.6, 4.7).

``none``, ``cross_encoder``, and ``flashrank`` are local and run without any paid API
call (Req 9.4, 22.3). ``cohere`` is key-gated. All rerankers cap their output to
``rerank_top_k`` (Req 4.6). A key-gated reranker raises naming the missing key rather
than silently falling back (Req 4.8, 9.4).
"""
from __future__ import annotations

import os

from rag.interfaces import Chunk, Reranker, source_prefixed_text as _titled_text


class MissingApiKeyError(Exception):
    """Raised when a key-gated reranker/LLM is selected without its required key."""

    def __init__(self, env_key: str, module: str):
        self.env_key = env_key
        self.module = module
        super().__init__(f"'{module}' requires the environment key '{env_key}', which is not set.")


class NoneReranker(Reranker):
    """Passes through retrieval order, capped to rerank_top_k (Req 4.7)."""

    is_local = True

    def rerank(self, question: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        return list(chunks)[:top_k]


class CrossEncoderReranker(Reranker):
    """Local cross-encoder reranker (ms-marco-MiniLM), free (Req 9.4, 22.3)."""

    is_local = True

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model_name = model_name
        self._model = None

    def _ensure_loaded(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)

    def rerank(self, question: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        if not chunks:
            return []
        self._ensure_loaded()
        pairs = [(question, _titled_text(c)) for c in chunks]
        scores = self._model.predict(pairs)
        order = sorted(range(len(chunks)), key=lambda i: -scores[i])
        return [chunks[i] for i in order[:top_k]]


class FlashRankReranker(Reranker):
    """Local FlashRank reranker (CPU, ONNX), free (Req 9.4, 22.3)."""

    is_local = True

    def __init__(self):
        self._ranker = None

    def _ensure_loaded(self):
        if self._ranker is None:
            from flashrank import Ranker
            self._ranker = Ranker()

    def rerank(self, question: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        if not chunks:
            return []
        self._ensure_loaded()
        from flashrank import RerankRequest

        passages = [{"id": i, "text": _titled_text(c)} for i, c in enumerate(chunks)]
        request = RerankRequest(query=question, passages=passages)
        results = self._ranker.rerank(request)
        ordered = sorted(results, key=lambda r: -r["score"])[:top_k]
        return [chunks[r["id"]] for r in ordered]


class CohereReranker(Reranker):
    """Cohere Rerank API — key-gated (Req 4.8, 9.4)."""

    is_local = False

    def __init__(self, model: str = "rerank-english-v3.0"):
        self.model = model

    def rerank(self, question: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        if not os.getenv("COHERE_API_KEY"):
            raise MissingApiKeyError("COHERE_API_KEY", "rag.rerank.CohereReranker")
        if not chunks:
            return []
        import cohere

        client = cohere.Client(os.environ["COHERE_API_KEY"])
        docs = [_titled_text(c) for c in chunks]
        resp = client.rerank(model=self.model, query=question, documents=docs, top_n=min(top_k, len(docs)))
        return [chunks[r.index] for r in resp.results]


class LlmListwiseReranker(Reranker):
    """LLM listwise rerank: asks the variant's LLM to rank chunk ids by relevance."""

    is_local = False

    def rerank_with_llm(self, question: str, chunks: list[Chunk], top_k: int, llm) -> list[Chunk]:
        if not chunks:
            return []
        listing = "\n".join(f"[{i}] {_titled_text(c)[:300]}" for i, c in enumerate(chunks))
        prompt = (
            f"Question: {question}\n\nCandidate passages:\n{listing}\n\n"
            f"List the indices of the {min(top_k, len(chunks))} most relevant passages, "
            "most relevant first, comma-separated, indices only."
        )
        result = llm.generate(prompt, context_chunks=[])
        indices = []
        for tok in result.answer.replace("[", "").replace("]", "").split(","):
            tok = tok.strip()
            if tok.isdigit() and int(tok) < len(chunks):
                indices.append(int(tok))
        if not indices:
            return list(chunks)[:top_k]
        seen = set()
        ordered = []
        for i in indices:
            if i not in seen:
                seen.add(i)
                ordered.append(chunks[i])
        return ordered[:top_k]

    def rerank(self, question: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        raise RuntimeError("LlmListwiseReranker.rerank_with_llm(question, chunks, top_k, llm) requires an LLM.")


def make_reranker(name: str) -> Reranker:
    """Construct the Reranker registered under ``name`` (Req 1.1, 4.6, 4.7)."""
    if name == "none":
        return NoneReranker()
    if name == "cross_encoder":
        return CrossEncoderReranker()
    if name == "flashrank":
        return FlashRankReranker()
    if name == "cohere":
        return CohereReranker()
    if name == "llm_listwise":
        return LlmListwiseReranker()
    raise ValueError(f"Unknown reranker option: '{name}'")
