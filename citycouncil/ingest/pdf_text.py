"""PyMuPDF text extraction and chunking (TXT-101)."""

from __future__ import annotations

from typing import Any


def scan_pdf_metadata(pdf_bytes: bytes) -> dict[str, Any]:
    """Page count and total stripped text length (TXT-103: detect empty / likely scans)."""
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        n = len(doc)
        total = 0
        for i in range(n):
            total += len(doc[i].get_text().strip())
        return {
            "page_count": n,
            "total_text_chars": total,
            "likely_has_text": total > 0,
        }
    finally:
        doc.close()


def extract_pdf_text_per_page(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Return ``(page_number_1based, text)`` for each page with non-empty text."""
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        out: list[tuple[int, str]] = []
        for i in range(len(doc)):
            raw = doc[i].get_text()
            t = raw.strip()
            if t:
                out.append((i + 1, t))
        return out
    finally:
        doc.close()


def chunk_page_texts(
    pages: list[tuple[int, str]],
    max_chars: int,
) -> list[tuple[int | None, str]]:
    """Split long pages into multiple chunks. ``page_number`` is the first page for each chunk."""
    if max_chars < 256:
        raise ValueError("max_chars must be at least 256")
    chunks: list[tuple[int | None, str]] = []
    for page_num, text in pages:
        if len(text) <= max_chars:
            chunks.append((page_num, text))
            continue
        start = 0
        while start < len(text):
            chunks.append((page_num, text[start : start + max_chars]))
            start += max_chars
    return chunks


def extract_pdf_chunks(pdf_bytes: bytes, max_chars: int) -> list[tuple[int | None, str]]:
    """Full pipeline: PDF bytes → ordered chunks with page hints."""
    pages = extract_pdf_text_per_page(pdf_bytes)
    return chunk_page_texts(pages, max_chars)
