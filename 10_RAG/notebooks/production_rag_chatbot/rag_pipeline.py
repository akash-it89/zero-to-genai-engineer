"""
Production RAG pipeline \u2014 the exact class assembled in Notebook 13, saved as an
importable module so both the notebook and the Streamlit app (app.py) share one
implementation instead of drifting apart.

Pipeline: parse -> chunk -> hybrid index (dense Chroma/bge-small + sparse BM25)
-> RRF fuse -> cross-encoder rerank -> grounded, cited generation
-> groundedness guardrail -> conversational memory (condense-question pattern).
"""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import bm25s
from Stemmer import Stemmer
from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI

try:
    from langchain_pymupdf4llm import PyMuPDF4LLMLoader
    HAS_PYMUPDF4LLM = True
except ImportError:
    HAS_PYMUPDF4LLM = False


ANSWER_PROMPT = '''You are a careful assistant answering questions ONLY using the numbered sources below.
- Cite sources inline like [1], [2] after every claim they support.
- If the sources don\'t contain the answer, say so plainly \u2014 never guess.

Sources:
{sources}

Conversation so far:
{history}

Question: {question}

Answer (with inline citations):'''

CONDENSE_PROMPT = '''Given the recent conversation and a follow-up question, decide whether the
follow-up depends on the conversation (uses a pronoun or implicit reference like "it", "that",
"those", "the previous one") to make sense.

- If it DOES depend on the conversation, rewrite it as a standalone question that replaces the
  reference with the actual thing it refers to.
- If it does NOT depend on the conversation \u2014 including if it\'s simply a new question on a
  different topic \u2014 return it EXACTLY UNCHANGED. Do not "helpfully" relate an unrelated
  question back to the previous topic.

Conversation:
{history}

Follow-up question: {question}

Standalone question:'''


def load_document(path: str) -> list[dict]:
    """Parse one file into a list of {text, source, page} records \u2014 one per page."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        docs = (PyMuPDF4LLMLoader(str(path), table_strategy="lines").load()
                if HAS_PYMUPDF4LLM else PyPDFLoader(str(path)).load())
    elif suffix == ".docx":
        docs = Docx2txtLoader(str(path)).load()
    elif suffix in (".txt", ".md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        return [{"text": text, "source": path.name, "page": 1}]
    else:
        raise ValueError(f"Unsupported file type: {suffix!r} \u2014 use .pdf, .docx, .txt, or .md")

    return [
        {"text": d.page_content, "source": path.name, "page": d.metadata.get("page", 0) + 1}
        for d in docs if d.page_content.strip()
    ]


def chunk_documents(pages, chunk_size=500, chunk_overlap=80):
    """Split parsed pages into overlapping chunks; keep source + page for citations."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = []
    for page in pages:
        for piece in splitter.split_text(page["text"]):
            chunks.append({"text": piece, "source": page["source"], "page": page["page"]})
    return chunks


class HybridIndex:
    """Dense (Chroma + bge-small) + sparse (BM25) index, fused with RRF at query time."""

    def __init__(self, collection_name="rag_chatbot"):
        self.encoder = SentenceTransformer("BAAI/bge-small-en-v1.5")
        self.stemmer = Stemmer("english")
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection(
            collection_name, metadata={"hnsw:space": "cosine"}
        )
        self.chunks = []
        self.bm25 = None
        self._doc_emb = None

    def _tokenize(self, texts):
        return bm25s.tokenize(texts, stopwords="en", stemmer=self.stemmer.stemWords, return_ids=False, show_progress=False)

    def build(self, chunks):
        self.chunks = chunks
        texts = [c["text"] for c in chunks]
        ids = [str(uuid.uuid4()) for _ in chunks]
        for c, cid in zip(chunks, ids):
            c["id"] = cid

        vecs = self.encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        metadatas = [{"source": c["source"], "page": c["page"]} for c in chunks]
        self.collection.add(embeddings=vecs.tolist(), documents=texts, metadatas=metadatas, ids=ids)
        self._doc_emb = vecs

        self.bm25 = bm25s.BM25(method="lucene")
        self.bm25.index(self._tokenize(texts), show_progress=False)

    def _dense_order(self, query):
        q = self.encoder.encode([query], normalize_embeddings=True)[0]
        return list(np.argsort(q @ self._doc_emb.T)[::-1])

    def _sparse_order(self, query):
        scores = self.bm25.get_scores(self._tokenize([query])[0])
        return list(np.argsort(scores)[::-1])

    def search(self, query, k=8, rrf_k=60):
        """Reciprocal Rank Fusion of the dense and sparse rankings."""
        rankings = [self._dense_order(query), self._sparse_order(query)]
        scores = {}
        for ranking in rankings:
            for rank, idx in enumerate(ranking):
                scores[idx] = scores.get(idx, 0.0) + 1.0 / (rrf_k + rank)
        fused = sorted(scores, key=scores.get, reverse=True)[:k]
        return [self.chunks[i] for i in fused]


class Reranker:
    """Cross-encoder second stage over the fused candidates."""

    def __init__(self, model_name="cross-encoder/ms-marco-MiniLM-L6-v2"):
        try:
            self.model = CrossEncoder(model_name)
        except Exception:
            self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def rerank(self, query, candidates, top_n=4):
        pairs = [(query, c["text"]) for c in candidates]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [(c, float(s)) for c, s in ranked[:top_n]]


def format_sources(reranked):
    return "\n".join(f"[{i + 1}] ({c['source']}, p.{c['page']}) {c['text']}" for i, (c, _) in enumerate(reranked))


@dataclass
class ChatTurn:
    role: str
    content: str


class ProductionRAGChatbot:
    """
    parse -> chunk -> hybrid index (dense+sparse) -> RRF fuse -> cross-encoder rerank
    -> grounded, cited generation -> guarded against ungrounded answers -> memory-aware.
    """

    def __init__(self, chunk_size=500, chunk_overlap=80, top_k=8, top_n=4,
                 min_rerank_score=-9.5, model="gpt-4o-mini"):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.top_n = top_n
        self.min_rerank_score = min_rerank_score
        self.index = HybridIndex()
        self.reranker = Reranker()
        self.llm = ChatOpenAI(model=model, temperature=0)
        self.history: list[ChatTurn] = []

    def ingest(self, file_paths):
        """Parse + chunk one or more files, then build the hybrid index."""
        all_pages = []
        for path in file_paths:
            all_pages.extend(load_document(path))
        chunks = chunk_documents(all_pages, self.chunk_size, self.chunk_overlap)
        self.index.build(chunks)
        return {"files": len(file_paths), "pages": len(all_pages), "chunks": len(chunks)}

    def _history_pairs(self):
        return [(t.role, t.content) for t in self.history]

    def _condense(self, question):
        if not self.history:
            return question
        history_text = "\n".join(f"{role}: {content}" for role, content in self._history_pairs()[-6:])
        return self.llm.invoke(CONDENSE_PROMPT.format(history=history_text, question=question)).content.strip()

    def chat(self, question):
        standalone = self._condense(question)
        candidates = self.index.search(standalone, k=self.top_k)
        reranked = self.reranker.rerank(standalone, candidates, top_n=self.top_n)

        if not reranked or reranked[0][1] < self.min_rerank_score:
            answer = "I don\'t have enough information in the uploaded document(s) to answer that confidently."
            sources = []
        else:
            history_text = "\n".join(f"{t.role}: {t.content}" for t in self.history[-6:])
            prompt = ANSWER_PROMPT.format(
                sources=format_sources(reranked), history=history_text, question=standalone
            )
            answer = self.llm.invoke(prompt).content.strip()
            sources = [
                {"rank": i + 1, "source": c["source"], "page": c["page"], "score": round(s, 3), "text": c["text"]}
                for i, (c, s) in enumerate(reranked)
            ]

        self.history.append(ChatTurn("user", question))
        self.history.append(ChatTurn("assistant", answer))
        return {"answer": answer, "sources": sources, "standalone_question": standalone}

    def naive_chat(self, question):
        """The Section 2 baseline, reusing the SAME index: top-1 dense-only, no rerank,
        no guardrail, no citations, no memory. For side-by-side comparison only."""
        order = self.index._dense_order(question)
        top_chunk = self.index.chunks[order[0]]
        prompt = f"Answer using this context:\n\n{top_chunk['text']}\n\nQuestion: {question}\nAnswer:"
        answer = self.llm.invoke(prompt).content.strip()
        return {"answer": answer, "source": {"source": top_chunk["source"], "page": top_chunk["page"]}}
