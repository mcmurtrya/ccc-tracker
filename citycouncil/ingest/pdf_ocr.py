"""OCR fallback for scanned PDFs (TXT-103) using PyMuPDF render + Tesseract."""

from __future__ import annotations

import logging

from citycouncil.ingest.pdf_text import chunk_page_texts

logger = logging.getLogger(__name__)


def extract_pdf_ocr_chunks(pdf_bytes: bytes, max_chars: int, dpi: int = 150) -> list[tuple[int | None, str]]:
    """Render each page to a bitmap and OCR with Tesseract; then chunk like PyMuPDF text."""
    import pymupdf
    import pytesseract
    from PIL import Image

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages: list[tuple[int, str]] = []
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(dpi=dpi)
            mode = "RGB" if pix.n < 4 else "RGBA"
            img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            if img.mode != "RGB":
                img = img.convert("RGB")
            text = pytesseract.image_to_string(img)
            t = (text or "").strip()
            if t:
                pages.append((i + 1, t))
        return chunk_page_texts(pages, max_chars)
    finally:
        doc.close()
