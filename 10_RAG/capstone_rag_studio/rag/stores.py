"""Embedders and VectorStore options (Req 4.1, 9.5, 22.3, 23.4).

``memory`` and local embedders (``bge-small``, ``minilm``) execute without any paid
API call (Req 9.5, 22.3). ``chroma`` persists to disk (Req 23.4); ``faiss`` is an
in-process ANN index; ``pinecone`` is key-gated and only constructed when
``PINECONE_API_KEY`` is present.

Only :mod:`rag.interfaces` is imported at module import time; provider SDKs
(sentence-transformers, chromadb, faiss, pinecone, openai) are imported lazily inside
factory functions/constructors so ``rag`` stays light to import (Req 10.1, 12.6).
"""
from __future__ import annotations

import functools
from typing import Sequence

import numpy as np

from rag.interfaces import Candidate, Chunk, Embedder, VectorStore


# ---------------------------------------------------------------------------
# Embedders (Req 22.3 — local embedders record zero cost)
# ---------------------------------------------------------------------------

class LocalSentenceTransformerEmbedder(Embedder):
    """Local, free embedder backed by sentence-transformers (Req 9.5, 22.3)."""

    is_local = True

    def __init__(self, model_name: str, dim: int):
        from sentence_transformers import SentenceTransformer  # lazy import
        self._model = SentenceTransformer(model_name)
        self.dim = dim

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        vecs = self._model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)


class OpenAIEmbedder(Embedder):
    """OpenAI embeddings API (Req 9.2 — requires OPENAI_API_KEY)."""

    is_local = False

    def __init__(self, model_name: str, dim: int):
        self.model_name = model_name
        self.dim = dim

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        from openai import OpenAI  # lazy import
        client = OpenAI()
        resp = client.embeddings.create(model=self.model_name, input=list(texts))
        vecs = np.asarray([d.embedding for d in resp.data], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms


def make_embedder(name: str) -> Embedder:
    """Construct the Embedder registered under ``name`` (Req 1.1, 9.2, 9.5)."""
    from rag import registry as R

    opt = R.get_option("embedding", name)
    if opt is None:
        raise ValueError(f"Unknown embedding option: '{name}'")
    meta = opt.meta
    if opt.is_local:
        return LocalSentenceTransformerEmbedder(meta["model"], meta["dim"])
    return OpenAIEmbedder(meta["model"], meta["dim"])


# ---------------------------------------------------------------------------
# VectorStore implementations (Req 4.1, 22.3, 23.4)
# ---------------------------------------------------------------------------

def _cosine_search(query_vec: np.ndarray, matrix: np.ndarray, chunks: list[Chunk], k: int) -> list[Candidate]:
    if matrix.shape[0] == 0:
        return []
    q = query_vec / (np.linalg.norm(query_vec) or 1.0)
    m_norms = np.linalg.norm(matrix, axis=1)
    m_norms[m_norms == 0] = 1.0
    sims = (matrix @ q) / m_norms
    order = np.argsort(-sims)[:k]
    return [Candidate(chunk=chunks[i], score=float(sims[i]), rank=rank) for rank, i in enumerate(order)]


class MemoryVectorStore(VectorStore):
    """In-memory NumPy cosine-similarity store — free, no persistence (Req 22.3)."""

    is_local = True

    def __init__(self):
        self._vectors: list[np.ndarray] = []
        self._chunks: list[Chunk] = []
        self._ids: list[str] = []

    def add(self, ids: Sequence[str], vectors, chunks: Sequence[Chunk]) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        for i, vec, chunk in zip(ids, vectors, chunks):
            self._ids.append(i)
            self._vectors.append(vec)
            self._chunks.append(chunk)

    def search(self, query_vec, k: int) -> list[Candidate]:
        if not self._vectors:
            return []
        matrix = np.stack(self._vectors)
        return _cosine_search(np.asarray(query_vec, dtype=np.float32), matrix, self._chunks, k)


class ChromaVectorStore(VectorStore):
    """Persistent Chroma store — local, free (Req 22.3, 23.4)."""

    is_local = True

    def __init__(self, persist_dir: str, collection_name: str = "rag_studio"):
        import chromadb  # lazy import
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(collection_name)
        self._chunks_by_id: dict[str, Chunk] = {}

    def add(self, ids: Sequence[str], vectors, chunks: Sequence[Chunk]) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        for i, chunk in zip(ids, chunks):
            self._chunks_by_id[i] = chunk
        self._collection.add(
            ids=list(ids),
            embeddings=vectors.tolist(),
            documents=[c.text for c in chunks],
            metadatas=[{"source": c.source} for c in chunks],
        )

    def search(self, query_vec, k: int) -> list[Candidate]:
        query_vec = np.asarray(query_vec, dtype=np.float32)
        res = self._collection.query(
            query_embeddings=[query_vec.tolist()], n_results=max(k, 1),
            include=["documents", "metadatas", "distances"],
        )
        ids = res.get("ids", [[]])[0]
        distances = res.get("distances", [[]])[0]
        documents = res.get("documents", [[]])[0]
        metadatas = res.get("metadatas", [[]])[0]
        out = []
        for rank, (cid, dist, doc_text, meta) in enumerate(zip(ids, distances, documents, metadatas)):
            # Reconstruct the Chunk from Chroma's own persisted document+metadata when
            # this process never saw it via `add()` — e.g. after a restart, when only
            # the on-disk collection (not the in-memory cache) survives (Req 23.4).
            chunk = self._chunks_by_id.get(cid)
            if chunk is None:
                chunk = Chunk(id=cid, text=doc_text, source=(meta or {}).get("source", ""))
                self._chunks_by_id[cid] = chunk
            score = 1.0 - float(dist)   # cosine distance -> similarity
            out.append(Candidate(chunk=chunk, score=score, rank=rank))
        return out[:k]

    def persist(self) -> None:
        # PersistentClient auto-persists on write; no-op kept for interface symmetry.
        return None


class FaissVectorStore(VectorStore):
    """In-process FAISS ANN index — local, free (Req 22.3)."""

    is_local = True

    def __init__(self, dim: int):
        import faiss  # lazy import
        self._dim = dim
        self._index = faiss.IndexFlatIP(dim)
        self._chunks: list[Chunk] = []

    def add(self, ids: Sequence[str], vectors, chunks: Sequence[Chunk]) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._index.add(vectors / norms)
        self._chunks.extend(chunks)

    def search(self, query_vec, k: int) -> list[Candidate]:
        if self._index.ntotal == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32)
        q = q / (np.linalg.norm(q) or 1.0)
        scores, idxs = self._index.search(q.reshape(1, -1), min(k, self._index.ntotal))
        out = []
        for rank, (score, idx) in enumerate(zip(scores[0], idxs[0])):
            if idx < 0:
                continue
            out.append(Candidate(chunk=self._chunks[idx], score=float(score), rank=rank))
        return out


class PineconeVectorStore(VectorStore):
    """Managed Pinecone store — key-gated, only constructed when the key is present."""

    is_local = False

    def __init__(self, index_name: str, dim: int):
        import os

        if not os.getenv("PINECONE_API_KEY"):
            raise RuntimeError("PineconeVectorStore requires the 'PINECONE_API_KEY' environment key.")
        from pinecone import Pinecone, ServerlessSpec  # lazy import

        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        if index_name not in [i["name"] for i in pc.list_indexes()]:
            pc.create_index(
                name=index_name, dimension=dim, metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        self._index = pc.Index(index_name)
        self._chunks_by_id: dict[str, Chunk] = {}

    def add(self, ids: Sequence[str], vectors, chunks: Sequence[Chunk]) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        vecs = []
        for i, vec, chunk in zip(ids, vectors, chunks):
            self._chunks_by_id[i] = chunk
            vecs.append({"id": i, "values": vec.tolist(), "metadata": {"source": chunk.source}})
        self._index.upsert(vectors=vecs)

    def search(self, query_vec, k: int) -> list[Candidate]:
        query_vec = np.asarray(query_vec, dtype=np.float32)
        res = self._index.query(vector=query_vec.tolist(), top_k=k, include_metadata=False)
        out = []
        for rank, match in enumerate(res.get("matches", [])):
            chunk = self._chunks_by_id.get(match["id"])
            if chunk is None:
                continue
            out.append(Candidate(chunk=chunk, score=float(match["score"]), rank=rank))
        return out


def make_vector_store(name: str, *, dim: int = 384, persist_dir: str = ".chroma", index_name: str = "rag-studio") -> VectorStore:
    """Construct the VectorStore registered under ``name`` (Req 1.1, 4.1, 9.5)."""
    if name == "memory":
        return MemoryVectorStore()
    if name == "chroma":
        return ChromaVectorStore(persist_dir)
    if name == "faiss":
        return FaissVectorStore(dim)
    if name == "pinecone":
        return PineconeVectorStore(index_name, dim)
    raise ValueError(f"Unknown vector_store option: '{name}'")
