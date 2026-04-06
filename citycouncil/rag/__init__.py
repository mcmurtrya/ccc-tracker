"""RAG: semantic search over embedded document chunks."""

from citycouncil.rag.search import (
    ChunkCitation,
    ChunkSearchHit,
    DocumentSnippet,
    MeetingSnippet,
    body_preview,
    citations_from_chunk_results,
    search_document_chunks,
)

__all__ = [
    "ChunkCitation",
    "ChunkSearchHit",
    "DocumentSnippet",
    "MeetingSnippet",
    "body_preview",
    "citations_from_chunk_results",
    "search_document_chunks",
]
