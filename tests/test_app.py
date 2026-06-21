from unittest.mock import Mock, patch

import pytest
import requests

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def _mock_response(text, status_ok=True):
    resp = Mock()
    resp.text = text
    resp.raise_for_status = Mock(side_effect=None if status_ok else requests.HTTPError("boom"))
    return resp


def test_index_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_missing_code_returns_400(client):
    resp = client.get("/api/metar")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


@pytest.mark.parametrize("bad_code", ["", "AB", "TOOLONG", "K!F"])
def test_invalid_code_returns_400(client, bad_code):
    resp = client.get(f"/api/metar?code={bad_code}")
    assert resp.status_code == 400


@patch("app.requests.get")
def test_valid_code_returns_decoded_metar(mock_get, client):
    raw = "KJFK 190951Z 30011KT 10SM SCT170 BKN250 23/11 A2968"
    mock_get.return_value = _mock_response(raw)

    resp = client.get("/api/metar?code=kjfk")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["station"] == "KJFK"
    assert data["raw"] == raw
    assert "summary" in data
    assert "details" in data
    assert "icon" in data

    called_kwargs = mock_get.call_args.kwargs
    assert called_kwargs["params"]["ids"] == "KJFK"


@patch("app.requests.get")
def test_unknown_station_returns_404(mock_get, client):
    mock_get.return_value = _mock_response("")

    resp = client.get("/api/metar?code=ZZZZ")
    assert resp.status_code == 404
    assert "ZZZZ" in resp.get_json()["error"]


@patch("app.requests.get")
def test_network_failure_returns_502(mock_get, client):
    mock_get.side_effect = requests.ConnectionError("network down")

    resp = client.get("/api/metar?code=KJFK")
    assert resp.status_code == 502


@patch("app.requests.get")
def test_upstream_http_error_returns_502(mock_get, client):
    mock_get.return_value = _mock_response("ignored", status_ok=False)

    resp = client.get("/api/metar?code=KJFK")
    assert resp.status_code == 502
