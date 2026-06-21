"""End-to-end tests of the /api/metar route, with the aviationweather.gov
call mocked. Unlike test_app.py's status-code checks, these assert the full
JSON payload matches what the decoder independently produces for the same
raw report, proving the route and the decoder are wired together correctly.
"""
from unittest.mock import Mock, patch

import pytest
import requests

from app import app
from metar_decoder import decode_metar

SCENARIOS = [
    pytest.param(
        "KJFK", "METAR KJFK 190951Z 30011KT 10SM SCT170 BKN250 23/11 A2968 RMK AO2",
        id="clear-with-scattered-and-broken-cloud",
    ),
    pytest.param(
        "KDEN", "KDEN 191751Z 27015G25KT 1 1/2SM +TSRA BKN030CB 28/18 A2995",
        id="thunderstorm-with-gusts",
    ),
    pytest.param(
        "KBOS", "KBOS 191754Z 18006KT 1/2SM -RASN BR BKN008 OVC015 M02/M05 A2980 RMK",
        id="mixed-rain-snow-and-mist",
    ),
    pytest.param(
        "KORD", "KORD 191751Z 00000KT M1/4SM FG VV002 05/05 A3001",
        id="calm-fog-indefinite-ceiling",
    ),
    pytest.param(
        "EGLL", "EGLL 191750Z VRB03KT 9999 FEW020 18/10 Q1015",
        id="international-hpa-altimeter",
    ),
]


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def _mock_get(raw_text):
    resp = Mock()
    resp.text = raw_text
    resp.raise_for_status = Mock()
    return Mock(return_value=resp)


@pytest.mark.parametrize("code, raw", SCENARIOS)
def test_full_response_matches_decoder_output(client, code, raw):
    with patch("app.requests.get", _mock_get(raw)) as mock_get:
        # lowercase + surrounding whitespace, to exercise normalization end-to-end
        resp = client.get(f"/api/metar?code=  {code.lower()}  ")

    assert resp.status_code == 200
    data = resp.get_json()

    expected = decode_metar(raw)
    assert data["station"] == code
    assert data["raw"] == raw.strip()
    assert data["summary"] == expected["summary"]
    assert data["icon"] == expected["icon"]
    assert [tuple(pair) for pair in data["details"]] == expected["details"]

    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"ids": code, "format": "raw"}
    assert kwargs["timeout"] == 10


def test_response_is_json_serializable_end_to_end(client):
    raw = "KJFK 190951Z 30011KT 10SM SCT170 BKN250 23/11 A2968"
    with patch("app.requests.get", _mock_get(raw)):
        resp = client.get("/api/metar?code=KJFK")

    assert resp.content_type == "application/json"
    data = resp.get_json()
    assert set(data.keys()) == {"station", "raw", "summary", "details", "icon"}


def test_unknown_station_full_error_flow(client):
    with patch("app.requests.get", _mock_get("")):
        resp = client.get("/api/metar?code=ZZZZ")

    assert resp.status_code == 404
    data = resp.get_json()
    assert "ZZZZ" in data["error"]
    assert "ICAO" in data["error"]


@pytest.mark.parametrize(
    "exception",
    [requests.ConnectionError("down"), requests.Timeout("slow"), requests.HTTPError("500")],
)
def test_upstream_failures_surface_as_friendly_502(client, exception):
    with patch("app.requests.get", Mock(side_effect=exception)):
        resp = client.get("/api/metar?code=KJFK")

    assert resp.status_code == 502
    assert "try again" in resp.get_json()["error"].lower()


def test_sequential_lookups_for_different_airports_are_independent(client):
    first_raw = "KJFK 190951Z 30011KT 10SM SCT170 BKN250 23/11 A2968"
    second_raw = "KDEN 191751Z 27015G25KT 1 1/2SM +TSRA BKN030CB 28/18 A2995"

    with patch("app.requests.get", _mock_get(first_raw)):
        first_resp = client.get("/api/metar?code=KJFK").get_json()

    with patch("app.requests.get", _mock_get(second_raw)):
        second_resp = client.get("/api/metar?code=KDEN").get_json()

    assert first_resp["station"] == "KJFK"
    assert second_resp["station"] == "KDEN"
    assert first_resp["summary"] != second_resp["summary"]
