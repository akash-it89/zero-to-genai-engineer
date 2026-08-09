"""Cache options: cross-cutting result cache, principal+config scoped (Req 18).

``exact_match`` (default on) stores/returns results keyed by a sha256 hash of
(principal id, canonical config, question) — a hit requires byte-identical question
text (Req 18.2, 18.3). ``semantic`` additionally matches near-duplicate questions
within the same principal+config scope using a local (free) sentence-embedding
similarity, so it never makes a paid API call. ``off`` skips every read and write
(Req 18.1, 18.7). Only post-governance ``AnswerResult`` values are ever stored — the
orchestrator is responsible for calling ``put`` after governance/post-retrieval/rerank
have already run (Req 18.4).
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from rag.interfaces import AnswerResult, Cache, Principal


def _canonical_config_json(config_dict: dict) -> str:
    return json.dumps(config_dict, sort_keys=True, default=str)


def _scope_hash(principal: Principal, config_dict: dict) -> str:
    raw = f"{principal.id}:{_canonical_config_json(config_dict)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class OffCache(Cache):
    """Disabled: every read/write is a no-op (Req 18.1, 18.7)."""

    def key(self, principal: Principal, config_dict: dict, question: str) -> str:
        return ""

    def get(self, key: str) -> Optional[AnswerResult]:
        return None

    def put(self, key: str, result: AnswerResult) -> None:
        return None


class ExactMatchCache(Cache):
    """Default-on cache: sha256(principal id, canonical config, question) -> result
    (Req 18.2-18.6). A byte-different question is always a miss (P10)."""

    def __init__(self):
        self._store: dict[str, AnswerResult] = {}

    def key(self, principal: Principal, config_dict: dict, question: str) -> str:
        raw = f"{principal.id}:{_canonical_config_json(config_dict)}:{question}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[AnswerResult]:
        return self._store.get(key)

    def put(self, key: str, result: AnswerResult) -> None:
        self._store[key] = result


class SemanticCache(Cache):
    """Matches near-duplicate questions within the same principal+config scope via a
    local (free) sentence-embedding similarity — no paid API call (Req 9.5, 22.3).

    ``key()`` returns an opaque token combining the principal+config scope hash with
    the raw question text, since a similarity lookup needs the text itself rather
    than a pure hash; ``get``/``put`` parse it back out.
    """

    _KEY_SEP = ":::"

    def __init__(self, similarity_threshold: float = 0.92):
        self.similarity_threshold = similarity_threshold
        self._entries: dict[str, list[tuple[object, AnswerResult]]] = {}
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy import
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def _embed(self, text: str):
        self._ensure_model()
        return self._model.encode([text], normalize_embeddings=True)[0]

    def key(self, principal: Principal, config_dict: dict, question: str) -> str:
        return f"{_scope_hash(principal, config_dict)}{self._KEY_SEP}{question}"

    def get(self, key: str) -> Optional[AnswerResult]:
        scope, _, question = key.partition(self._KEY_SEP)
        entries = self._entries.get(scope, [])
        if not entries:
            return None
        import numpy as np

        q_vec = np.asarray(self._embed(question))
        best_sim, best_result = -1.0, None
        for emb, result in entries:
            sim = float(np.dot(q_vec, np.asarray(emb)))
            if sim > best_sim:
                best_sim, best_result = sim, result
        return best_result if best_sim >= self.similarity_threshold else None

    def put(self, key: str, result: AnswerResult) -> None:
        scope, _, question = key.partition(self._KEY_SEP)
        emb = self._embed(question)
        self._entries.setdefault(scope, []).append((emb, result))


def make_cache(name: str) -> Cache:
    """Construct the Cache registered under ``name`` (Req 1.1, 18)."""
    if name == "off":
        return OffCache()
    if name == "exact_match":
        return ExactMatchCache()
    if name == "semantic":
        return SemanticCache()
    raise ValueError(f"Unknown cache option: '{name}'")
