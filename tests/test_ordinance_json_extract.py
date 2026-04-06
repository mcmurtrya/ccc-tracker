from citycouncil.llm.ordinance_summarize import _extract_json_object


def test_extract_json_object_strips_fence() -> None:
    raw = '```json\n{"summary": "Hello.", "tags": ["zoning"]}\n```'
    assert _extract_json_object(raw) == {"summary": "Hello.", "tags": ["zoning"]}
