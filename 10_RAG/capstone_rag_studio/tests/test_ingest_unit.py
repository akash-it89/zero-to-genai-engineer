"""Feature: rag-studio — ingestion unit/example tests (Req 3.8, 3.9)."""
from __future__ import annotations

import pytest

from rag import ingest
from rag.ingest import ParseError, SemanticChunker, build_chunks


def test_semantic_chunking_falls_back_and_reports(monkeypatch):
    # Req 3.8: semantic chunking failure falls back to recursive AND is reported.
    import langchain_openai

    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("no embeddings backend in test")

    monkeypatch.setattr(langchain_openai, "OpenAIEmbeddings", _Boom)

    chunker = SemanticChunker()
    pieces = chunker.split("A sentence. " * 40, size=120, overlap=20)
    assert pieces                      # recursive fallback still produced chunks
    assert chunker.fell_back is True
    assert "recursive" in chunker.fallback_reason

    result = build_chunks(
        [{"text": "A sentence. " * 40, "source": "d0"}],
        strategy="semantic", chunk_size=120, chunk_overlap=20,
    )
    assert result.chunks
    assert any("d0" in note and "recursive" in note for note in result.notes)


def test_unsupported_extension_raises_parse_error():
    # Req 3.9: an unparseable/unknown file raises a descriptive error naming the file.
    with pytest.raises(ParseError) as excinfo:
        ingest.load_file("/tmp/whatever.xyz")
    assert "whatever.xyz" in str(excinfo.value)


def test_get_parser_for_known_extensions():
    # Format-appropriate parser selection (Req 3.1).
    assert ingest.get_parser_for("a.pdf").__class__.__name__ == "PdfParser"
    assert ingest.get_parser_for("a.html").__class__.__name__ == "HtmlParser"
    assert ingest.get_parser_for("a.docx").__class__.__name__ == "DocxParser"
    assert ingest.get_parser_for("a.txt").__class__.__name__ == "TxtParser"
    assert ingest.get_parser_for("a.png").__class__.__name__ == "OcrParser"
