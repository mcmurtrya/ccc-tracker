from citycouncil.llm.json_response import extract_json_object


def test_extract_json_object_strips_fence() -> None:
    raw = '```json\n{"summary": "Hello.", "tags": ["zoning"]}\n```'
    assert extract_json_object(raw) == {"summary": "Hello.", "tags": ["zoning"]}
