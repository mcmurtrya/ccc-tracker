from citycouncil.ingest.documents_sync import (
    _is_pdf_candidate,
    extract_elms_files_from_meeting_raw_json,
)


def test_extract_elms_files_from_bundle() -> None:
    raw = {
        "elms": {
            "files": [
                {"path": "https://example.com/a.pdf", "fileName": "Agenda.pdf", "attachmentType": "Agenda"}
            ]
        }
    }
    files = extract_elms_files_from_meeting_raw_json(raw)
    assert len(files) == 1
    assert files[0]["path"].endswith(".pdf")


def test_extract_elms_files_top_level_files() -> None:
    raw = {"files": [{"path": "https://x/y.pdf", "fileName": "y.pdf"}]}
    assert len(extract_elms_files_from_meeting_raw_json(raw)) == 1


def test_extract_empty() -> None:
    assert extract_elms_files_from_meeting_raw_json(None) == []
    assert extract_elms_files_from_meeting_raw_json({}) == []


def test_is_pdf_candidate() -> None:
    assert _is_pdf_candidate("https://x/a.PDF", None) is True
    assert _is_pdf_candidate("https://x/doc", "b.pdf") is True
    assert _is_pdf_candidate("https://x/doc", "x.txt") is False
