import pytest
import pymupdf

from citycouncil.ingest.pdf_text import (
    chunk_page_texts,
    extract_pdf_chunks,
    extract_pdf_text_per_page,
    scan_pdf_metadata,
)


def _minimal_pdf_bytes(text: str = "Hello Chicago Council") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    b = doc.tobytes()
    doc.close()
    return b


def test_extract_pdf_text_per_page() -> None:
    b = _minimal_pdf_bytes()
    pages = extract_pdf_text_per_page(b)
    assert len(pages) >= 1
    assert pages[0][0] == 1
    assert "Hello" in pages[0][1]


def test_extract_pdf_chunks_pipeline() -> None:
    b = _minimal_pdf_bytes("Line one.\nLine two.")
    chunks = extract_pdf_chunks(b, max_chars=4000)
    assert len(chunks) >= 1
    joined = " ".join(c[1] for c in chunks)
    assert "Line" in joined


def test_chunk_splits_long_page() -> None:
    long_text = "x" * 5000
    chunks = chunk_page_texts([(1, long_text)], max_chars=2000)
    assert len(chunks) == 3
    assert all(c[0] == 1 for c in chunks)


def test_chunk_max_chars_minimum() -> None:
    with pytest.raises(ValueError):
        chunk_page_texts([(1, "a")], max_chars=100)


def test_scan_pdf_metadata_blank_page() -> None:
    doc = pymupdf.open()
    doc.new_page()
    b = doc.tobytes()
    doc.close()
    meta = scan_pdf_metadata(b)
    assert meta["page_count"] >= 1
    assert meta["likely_has_text"] is False


def test_extract_pdf_chunks_blank_document() -> None:
    doc = pymupdf.open()
    doc.new_page()
    b = doc.tobytes()
    doc.close()
    assert extract_pdf_chunks(b, 4000) == []
