"""Ingestion + chunking, behind the Parser and Chunker Stage_Interfaces.

Parsers turn a file into clean text (Req 3.1-3.3, 3.9); Chunkers split text by the
chosen strategy (Req 3.4) with a graceful semantic->recursive fallback that is
reported (Req 3.8). ``build_chunks`` assigns each chunk a unique id, records its
source, inherits the source document's Access_Policy (Req 3.5), and excludes
sub-minimum-length fragments (Req 3.6).

Only :mod:`rag.interfaces` is imported from the package; provider libraries are
imported lazily inside methods so the module stays light to import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rag.interfaces import AccessPolicy, Chunk, Chunker, Parser

MIN_CHUNK_CHARS = 10   # minimum meaningful character count (Req 3.6)


class ParseError(Exception):
    """Raised when a file cannot be parsed; carries the file and reason (Req 3.9)."""

    def __init__(self, file: str, reason: str):
        self.file = file
        self.reason = reason
        super().__init__(f"Could not parse '{file}': {reason}")


# ---------------------------------------------------------------------------
# Parsers (Req 3.1-3.3)
# ---------------------------------------------------------------------------

class PdfParser(Parser):
    extensions = (".pdf",)

    def parse(self, path: str) -> str:
        try:
            import pymupdf4llm
            return pymupdf4llm.to_markdown(str(path))   # layout-aware, keeps tables (Req 3.2)
        except Exception:
            try:
                from langchain_community.document_loaders import PyPDFLoader
                return "\n".join(d.page_content for d in PyPDFLoader(str(path)).load())
            except Exception as exc:  # noqa: BLE001
                raise ParseError(str(path), f"PDF extraction failed: {exc}") from exc


class HtmlParser(Parser):
    extensions = (".html", ".htm")

    def parse(self, path: str) -> str:
        try:
            from langchain_community.document_loaders import BSHTMLLoader
            return BSHTMLLoader(str(path)).load()[0].page_content
        except Exception as exc:  # noqa: BLE001
            raise ParseError(str(path), f"HTML extraction failed: {exc}") from exc


class DocxParser(Parser):
    extensions = (".docx",)

    def parse(self, path: str) -> str:
        try:
            from langchain_community.document_loaders import Docx2txtLoader
            return Docx2txtLoader(str(path)).load()[0].page_content
        except Exception as exc:  # noqa: BLE001
            raise ParseError(str(path), f"DOCX extraction failed: {exc}") from exc


class TxtParser(Parser):
    extensions = (".txt", ".md")

    def parse(self, path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            raise ParseError(str(path), f"text read failed: {exc}") from exc


class OcrParser(Parser):
    extensions = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")

    def parse(self, path: str) -> str:
        try:
            from rapidocr_onnxruntime import RapidOCR
            result, _ = RapidOCR()(str(path))
            if not result:
                return ""
            return "\n".join(line[1] for line in result)   # OCR text (Req 3.3)
        except Exception as exc:  # noqa: BLE001
            raise ParseError(str(path), f"OCR failed: {exc}") from exc


_PARSERS: tuple[Parser, ...] = (PdfParser(), HtmlParser(), DocxParser(), TxtParser(), OcrParser())
_EXT_TO_PARSER: dict[str, Parser] = {ext: p for p in _PARSERS for ext in p.extensions}


def get_parser_for(path: str) -> Parser:
    ext = Path(path).suffix.lower()
    parser = _EXT_TO_PARSER.get(ext)
    if parser is None:
        raise ParseError(str(path), f"no parser registered for extension '{ext}'")
    return parser


def load_file(path: str) -> str:
    """Return clean text for a file, choosing a format-appropriate Parser."""
    return get_parser_for(path).parse(path)


# ---------------------------------------------------------------------------
# Chunkers (Req 3.4, 3.8)
# ---------------------------------------------------------------------------

class RecursiveChunker(Chunker):
    def split(self, text: str, size: int, overlap: int) -> list[str]:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        return RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap).split_text(text)


class TokenChunker(Chunker):
    def split(self, text: str, size: int, overlap: int) -> list[str]:
        from langchain_text_splitters import TokenTextSplitter
        return TokenTextSplitter(chunk_size=size, chunk_overlap=overlap).split_text(text)


class MarkdownChunker(Chunker):
    def split(self, text: str, size: int, overlap: int) -> list[str]:
        from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
        md = MarkdownHeaderTextSplitter([("#", "h1"), ("##", "h2"), ("###", "h3")], strip_headers=False)
        parts = md.split_text(text)
        rc = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
        return [c.page_content for c in rc.split_documents(parts)] or [text]


class SemanticChunker(Chunker):
    """Semantic splitting with a reported fallback to recursive (Req 3.8)."""

    def __init__(self):
        self.fell_back = False
        self.fallback_reason = ""

    def split(self, text: str, size: int, overlap: int) -> list[str]:
        try:
            from langchain_experimental.text_splitter import SemanticChunker as _SC
            from langchain_openai import OpenAIEmbeddings
            sc = _SC(OpenAIEmbeddings(model="text-embedding-3-small"),
                     breakpoint_threshold_type="percentile")
            return [d.page_content for d in sc.create_documents([text])]
        except Exception as exc:  # noqa: BLE001
            self.fell_back = True
            self.fallback_reason = f"semantic chunking unavailable ({exc}); fell back to recursive"
            return RecursiveChunker().split(text, size, overlap)


_CHUNKER_CLASSES = {
    "recursive": RecursiveChunker,
    "token": TokenChunker,
    "markdown": MarkdownChunker,
    "semantic": SemanticChunker,
}


def make_chunker(strategy: str) -> Chunker:
    cls = _CHUNKER_CLASSES.get(strategy, RecursiveChunker)
    return cls()


# ---------------------------------------------------------------------------
# build_chunks (Req 3.5, 3.6)
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    chunks: list[Chunk] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # e.g. semantic-fallback reports (Req 3.8)


def build_chunks(
    docs: list[dict],
    strategy: str = "recursive",
    chunk_size: int = 500,
    chunk_overlap: int = 60,
) -> IngestResult:
    """docs: [{'text','source', optional 'access_policy'}] -> IngestResult.

    Each produced Chunk gets a unique id, records its source, inherits that source's
    Access_Policy, and is excluded when shorter than ``MIN_CHUNK_CHARS``.
    """
    result = IngestResult()
    for d in docs:
        source = d.get("source", "doc")
        policy = d.get("access_policy") or AccessPolicy()
        chunker = make_chunker(strategy)
        pieces = chunker.split(d["text"], chunk_size, chunk_overlap)
        if getattr(chunker, "fell_back", False):
            result.notes.append(f"{source}: {chunker.fallback_reason}")
        for j, piece in enumerate(pieces):
            piece = piece.strip()
            if len(piece) < MIN_CHUNK_CHARS:      # exclude tiny fragments (Req 3.6)
                continue
            result.chunks.append(
                Chunk(id=f"{source}::{j}", text=piece, source=source, access_policy=policy)
            )
    return result
