from uuid import uuid4

import pytest
from assertive_mock_api_client.client import MockApiClient


class _FakeResponse:
    def __init__(self, *, json_payload=None, error: Exception | None = None):
        self._json_payload = json_payload or {}
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> dict:
        return self._json_payload


def test_new_session_enter_and_exit_calls_endpoints(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []
    stub_ids = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        stub_ids.append(stub_id := str(uuid4()))
        return _FakeResponse(json_payload={"success": True, "stub_id": stub_id})

    def fake_delete(url, headers=None):
        calls.append(("DELETE", url, None, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.delete", fake_delete)

    client = MockApiClient("http://localhost:8910")
    with client.new_session() as session:
        assert isinstance(session, MockApiClient)
        session.when_requested_with(method="GET", path="/test/1").respond_with_json(
            status_code=200, body={"success": True}
        )
        session.when_requested_with(method="GET", path="/test/2").respond_with_template(
            status_code=200, template_body="I am i template."
        )
        session.when_requested_with(method="GET", path="/test/2").respond_with_sse(
            events=[{"data": "foo"}]
        )

    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/__mock__/stubs")
    assert calls[1][0] == "POST"
    assert calls[1][1].endswith("/__mock__/stubs")
    assert calls[2][0] == "POST"
    assert calls[2][1].endswith("/__mock__/stubs")
    assert calls[3][0] == "DELETE"
    assert calls[3][1].endswith(f"/__mock__/stubs/{stub_ids[0]}")
    assert calls[4][0] == "DELETE"
    assert calls[4][1].endswith(f"/__mock__/stubs/{stub_ids[1]}")
    assert calls[5][0] == "DELETE"
    assert calls[5][1].endswith(f"/__mock__/stubs/{stub_ids[2]}")


def test_nested_sessions_on_session_are_disallowed():
    client = MockApiClient("http://localhost:8910")
    with client.new_session() as session:
        assert isinstance(session, MockApiClient)
        with pytest.raises(RuntimeError, match="Nested sessions are not supported"):
            with client.new_session() as session:
                ...
