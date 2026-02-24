import pytest
from pydantic import ValidationError

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


def test_scoped_create_template_stub_sends_template_body(monkeypatch):
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
        scoped.when_requested_with(path="/hello").respond_with_template(
            status_code=200,
            headers={},
            template_body="Hello {{ request.query.name }}",
        )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][3] == {"team_a": "1"}
    assert stub_calls[0][2] is not None
    response_payload = stub_calls[0][2]["action"]["response"]
    assert "body" not in response_payload
    assert response_payload["template_body"] == "Hello {{ request.query.name }}"


def test_scoped_create_sse_stub_sends_sse_payload(monkeypatch):
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
        scoped.when_requested_with(path="/events").respond_with_sse(
            events=[
                {"id": "1", "event": "message", "data": "first"},
                {"id": "2", "event": "message", "data": "second"},
            ],
            default_delay_ms=25,
        )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][3] == {"team_a": "1"}
    assert stub_calls[0][2] is not None
    action_payload = stub_calls[0][2]["action"]
    assert "response" not in action_payload
    assert "proxy" not in action_payload
    assert action_payload["sse"]["default_delay_ms"] == 25
    assert len(action_payload["sse"]["events"]) == 2


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


def test_with_chaos_on_response_stub_serializes_top_level_chaos(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/slow").with_latency(
        delay_ms=100,
        jitter_ms=50,
    ).respond_with(status_code=200, headers={}, body="ok")

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {"latency": {"base_ms": 100, "jitter_ms": 50}}


def test_with_chaos_defaults_jitter_to_zero(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/slow").with_latency(delay_ms=25).respond_with(
        status_code=200,
        headers={},
        body="ok",
    )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {"latency": {"base_ms": 25, "jitter_ms": 0}}


def test_with_chaos_applies_to_proxy_action(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/proxy").with_latency(
        delay_ms=10, jitter_ms=1
    ).proxy_to(
        url="https://example.com",
    )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {"latency": {"base_ms": 10, "jitter_ms": 1}}
    assert "proxy" in stub_calls[0][2]["action"]


def test_with_chaos_applies_to_sse_action(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/events").with_latency(
        delay_ms=5,
        jitter_ms=2,
    ).respond_with_sse(events=[{"data": "first"}])

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {"latency": {"base_ms": 5, "jitter_ms": 2}}
    assert "sse" in stub_calls[0][2]["action"]


def test_with_chaos_last_call_wins(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/slow").with_latency(delay_ms=10).with_latency(
        delay_ms=20,
        jitter_ms=5,
    ).respond_with(status_code=200, headers={}, body="ok")

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {"latency": {"base_ms": 20, "jitter_ms": 5}}


def test_with_chaos_rejects_negative_values():
    client = MockApiClient()

    with pytest.raises(ValidationError):
        client.when_requested_with(path="/slow").with_latency(delay_ms=-1)

    with pytest.raises(ValidationError):
        client.when_requested_with(path="/slow").with_latency(delay_ms=10, jitter_ms=-1)


def test_with_delay_alias_remains_supported(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    with pytest.warns(DeprecationWarning, match="with_delay"):
        client.when_requested_with(path="/slow").with_delay(
            delay_ms=15,
            jitter_ms=4,
        ).respond_with(status_code=200, headers={}, body="ok")

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {"latency": {"base_ms": 15, "jitter_ms": 4}}


def test_with_connection_drop_on_response_stub_serializes_nested_faults(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/unstable").with_connection_drop(
        probability=0.75
    ).respond_with(status_code=200, headers={}, body="ok")

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {
        "faults": {"connection_drop": {"probability": 0.75}}
    }


def test_with_connection_drop_applies_to_proxy_action(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/proxy").with_connection_drop(
        probability=0.2
    ).proxy_to(url="https://example.com")

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {
        "faults": {"connection_drop": {"probability": 0.2}}
    }
    assert "proxy" in stub_calls[0][2]["action"]


def test_with_connection_drop_applies_to_sse_action(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/events").with_connection_drop(
        probability=1.0
    ).respond_with_sse(events=[{"data": "first"}])

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {
        "faults": {"connection_drop": {"probability": 1.0}}
    }
    assert "sse" in stub_calls[0][2]["action"]


def test_with_connection_drop_last_call_wins(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/unstable").with_connection_drop(
        probability=0.1
    ).with_connection_drop(probability=0.9).respond_with(
        status_code=200, headers={}, body="ok"
    )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {
        "faults": {"connection_drop": {"probability": 0.9}}
    }


def test_with_connection_drop_rejects_out_of_range_probability():
    client = MockApiClient()

    with pytest.raises(ValidationError):
        client.when_requested_with(path="/unstable").with_connection_drop(
            probability=-0.1
        )

    with pytest.raises(ValidationError):
        client.when_requested_with(path="/unstable").with_connection_drop(
            probability=1.1
        )


def test_with_latency_then_connection_drop_merges_chaos(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/unstable").with_latency(
        delay_ms=20, jitter_ms=5
    ).with_connection_drop(probability=0.4).respond_with(
        status_code=200, headers={}, body="ok"
    )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {
        "latency": {"base_ms": 20, "jitter_ms": 5},
        "faults": {"connection_drop": {"probability": 0.4}},
    }


def test_with_connection_drop_then_delay_merges_chaos(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/unstable").with_connection_drop(
        probability=0.6
    ).with_latency(delay_ms=30, jitter_ms=0).respond_with(
        status_code=200, headers={}, body="ok"
    )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {
        "latency": {"base_ms": 30, "jitter_ms": 0},
        "faults": {"connection_drop": {"probability": 0.6}},
    }


def test_repeated_with_latency_preserves_connection_drop(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/unstable").with_connection_drop(
        probability=0.3
    ).with_latency(delay_ms=10).with_latency(delay_ms=40, jitter_ms=7).respond_with(
        status_code=200, headers={}, body="ok"
    )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {
        "latency": {"base_ms": 40, "jitter_ms": 7},
        "faults": {"connection_drop": {"probability": 0.3}},
    }


def test_repeated_with_connection_drop_preserves_latency(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/unstable").with_latency(
        delay_ms=50, jitter_ms=9
    ).with_connection_drop(probability=0.1).with_connection_drop(
        probability=0.8
    ).respond_with(status_code=200, headers={}, body="ok")

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert stub_calls[0][2]["chaos"] == {
        "latency": {"base_ms": 50, "jitter_ms": 9},
        "faults": {"connection_drop": {"probability": 0.8}},
    }


def test_without_with_chaos_payload_omits_chaos(monkeypatch):
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_post(url, json=None, headers=None):
        calls.append(("POST", url, json, headers))
        return _FakeResponse(json_payload={"success": True})

    monkeypatch.setattr("httpx.post", fake_post)

    client = MockApiClient()
    client.when_requested_with(path="/fast").respond_with(
        status_code=200,
        headers={},
        body="ok",
    )

    stub_calls = [call for call in calls if call[1].endswith("/__mock__/stubs")]
    assert len(stub_calls) == 1
    assert stub_calls[0][2] is not None
    assert "chaos" not in stub_calls[0][2]
