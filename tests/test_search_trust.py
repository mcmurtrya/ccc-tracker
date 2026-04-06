from citycouncil.rag.search import citations_from_chunk_results


def test_citations_from_chunk_results_shape() -> None:
    items = [
        {
            "chunk_id": "c1",
            "document_artifact_id": "d1",
            "meeting_id": "m1",
            "page_number": 2,
            "score": 0.9,
            "body": "x",
        }
    ]
    c = citations_from_chunk_results(items)
    assert len(c) == 1
    assert c[0]["chunk_id"] == "c1"
    assert c[0]["score"] == 0.9
    assert "body" not in c[0]


def test_citations_empty_input() -> None:
    assert citations_from_chunk_results([]) == []
