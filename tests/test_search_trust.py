from citycouncil.rag.search import ChunkSearchHit, citations_from_chunk_results


def test_citations_from_chunk_results_shape() -> None:
    items: list[ChunkSearchHit] = [
        {
            "chunk_id": "c1",
            "chunk_index": 0,
            "body": "x",
            "body_preview": "x",
            "page_number": 2,
            "meeting_id": "m1",
            "meeting": None,
            "document_artifact_id": "d1",
            "document": {"file_name": None, "source_url": None, "uri": None},
            "distance": 0.1,
            "score": 0.9,
        }
    ]
    c = citations_from_chunk_results(items)
    assert len(c) == 1
    assert c[0]["chunk_id"] == "c1"
    assert c[0]["score"] == 0.9
    assert "body" not in c[0]


def test_citations_empty_input() -> None:
    assert citations_from_chunk_results([]) == []
