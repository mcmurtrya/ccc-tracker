import pytest

from citycouncil.ingest.elms_adapter import adapt_elms_poll_response


def test_adapter_passes_through_fixture_shape() -> None:
    payload = {"meetings": [{"id": "x", "date": "2024-01-01", "members": []}]}
    assert adapt_elms_poll_response(payload) is payload


def test_adapter_maps_elms_data_array() -> None:
    raw = {
        "facets": [],
        "meta": {"skip": 0, "top": 100},
        "data": [
            {
                "meetingId": "2EA74F29-8923-F111-8341-001DD80B1275",
                "status": "Scheduled",
                "body": "City Council",
                "location": "Hall",
                "date": "2026-04-15T15:00:00+00:00",
                "agenda": None,
            }
        ],
    }
    out = adapt_elms_poll_response(raw)
    assert list(out.keys()) == ["meetings"]
    m = out["meetings"][0]
    assert m["id"] == "2EA74F29-8923-F111-8341-001DD80B1275"
    assert m["status"] == "Scheduled"
    assert m["members"] == []
    assert m["ordinances"] == []
    assert m["agenda_items"] == []
    assert m["votes"] == []
    assert m["elms"]["meetingId"] == "2EA74F29-8923-F111-8341-001DD80B1275"


def test_adapter_accepts_odata_value() -> None:
    raw = {
        "value": [
            {
                "meetingId": "a",
                "date": "2024-06-01",
                "body": "B",
                "location": "L",
                "status": "S",
            }
        ]
    }
    out = adapt_elms_poll_response(raw)
    assert len(out["meetings"]) == 1
    assert out["meetings"][0]["id"] == "a"


def test_adapter_rejects_unknown_shape() -> None:
    with pytest.raises(ValueError, match="meetings"):
        adapt_elms_poll_response({"foo": "bar"})


def test_adapter_requires_meeting_id() -> None:
    with pytest.raises(ValueError, match="meetingId"):
        adapt_elms_poll_response({"data": [{"date": "2024-01-01"}]})


def test_adapter_rejects_non_dict_meeting_row() -> None:
    with pytest.raises(TypeError, match="Expected meeting object dict"):
        adapt_elms_poll_response({"data": [123]})
