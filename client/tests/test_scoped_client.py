import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def test_new_scope_enter_and_exit_calls_scope_endpoints(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    def fake_delete(url, headers=None):
        calls.append(("DELETE", url, None, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.delete", fake_delete)

    client = MockApiClient("http://localhost:8910")
    with client.new_scope("team_a") as scoped:
        assert isinstance(scoped, MockApiClient)

    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/__mock__/scopes")
    assert calls[0][2] == {"name": "team_a"}
    assert calls[1][0] == "DELETE"
    assert calls[1][1].endswith("/__mock__/scopes/team_a")


def test_new_scope_create_conflict_raises_and_does_not_activate(monkeypatch):
    def fake_post(url, json=None, headers=None):
        return _FakeResponse(error=RuntimeError("409"))

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()

    with pytest.raises(RuntimeError, match="409"):
        with client.new_scope("team_a"):
            pass


def test_new_scope_delete_failure_raises_cleanup_error(monkeypatch):
    def fake_post(url, json=None, headers=None):
        return _FakeResponse(json_payload={"success": True})

    def fake_delete(url, headers=None):
        return _FakeResponse(error=RuntimeError("delete failed"))

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.delete", fake_delete)

    client = MockApiClient()

    with pytest.raises(RuntimeError, match="delete failed"):
        with client.new_scope("team_a"):
            pass


def test_scoped_create_stub_sends_scope_header(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    def fake_delete(url, headers=None):
        calls.append(("DELETE", url, None, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.delete", fake_delete)

    client = MockApiClient()

    with client.new_scope("team_a") as scoped:
        scoped.when_requested_with(path="/hello").respond_with(
            status_code=200,
            headers={},
            body="ok",
        )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][3] == {"team_a": "1"}


def test_scoped_confirm_request_sends_scope_header(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        if url.endswith("/__mock__/assert"):
            return _FakeResponse(json_payload={"result": True})
        return _FakeResponse(json_payload={"success": True})

    def fake_delete(url, headers=None):
        calls.append(("DELETE", url, None, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.delete", fake_delete)

    client = MockApiClient()

    with client.new_scope("team_a") as scoped:
        assert scoped.confirm_request(path="/hello") is True

    assert_calls = [call for call in calls if call[1].endswith("/__mock__/assert")]
    assert len(assert_calls) == 1
    assert assert_calls[0][3] == {"team_a": "1"}


def test_unscoped_create_stub_has_no_scope_header(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/hello").respond_with(
        status_code=200,
        headers={},
        body="ok",
    )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][3] == {}


def test_nested_scopes_on_scoped_client_are_disallowed(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    def fake_delete(url, headers=None):
        calls.append(("DELETE", url, None, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.delete", fake_delete)

    client = MockApiClient()

    with client.new_scope("outer") as outer:
        with pytest.raises(RuntimeError, match="Nested scopes are not supported"):
            with outer.new_scope("inner"):
                pass

    create_scope_calls = [
        call
        for call in calls
        if call[0] == "POST" and call[1].endswith("/__mock__/scopes")
    ]
    delete_scope_calls = [
        call
        for call in calls
        if call[0] == "DELETE" and call[1].endswith("/__mock__/scopes/outer")
    ]

    assert len(create_scope_calls) == 1
    assert len(delete_scope_calls) == 1


def test_parallel_scopes_on_root_client_are_allowed(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    def fake_delete(url, headers=None):
        calls.append(("DELETE", url, None, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.delete", fake_delete)

    client = MockApiClient()

    with client.new_scope("a") as scoped_a:
        with client.new_scope("b") as scoped_b:
            scoped_a.when_requested_with(path="/a").respond_with(
                status_code=200,
                headers={},
                body="a",
            )
            scoped_b.when_requested_with(path="/b").respond_with(
                status_code=200,
                headers={},
                body="b",
            )

    create_scope_calls = [
        call
        for call in calls
        if call[0] == "POST" and call[1].endswith("/__mock__/scopes")
    ]
    delete_scope_calls = [
        call for call in calls if call[0] == "DELETE" and "/__mock__/scopes/" in call[1]
    ]
    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]

    assert len(create_scope_calls) == 2
    assert len(delete_scope_calls) == 2
    assert stub_calls[0][3] == {"a": "1"}
    assert stub_calls[1][3] == {"b": "1"}
