from citycouncil.ingest.documents_extract import _ALLOWED_STATUS


def test_allowed_status_filters_documented() -> None:
    assert _ALLOWED_STATUS == {"pending", "failed", "pending_or_failed", "all"}
