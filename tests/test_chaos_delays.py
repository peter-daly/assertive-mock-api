import pytest
from fastapi.testclient import TestClient

import assertive_mock_api_server.core as core_module
from assertive_mock_api_server.app import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_stub_without_chaos_has_no_sleep_call(client: TestClient, monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    monkeypatch.setattr(core_module.asyncio, "sleep", fake_sleep)

    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-none", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
        },
    )
    assert create_response.status_code == 200

    response = client.get("/chaos-none")
    assert response.status_code == 200
    assert sleep_calls == []


def test_stub_with_fixed_delay_calls_sleep_once(client: TestClient, monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    monkeypatch.setattr(core_module.asyncio, "sleep", fake_sleep)

    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-fixed", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
            "chaos": {"latency": {"base_ms": 120, "jitter_ms": 0}},
        },
    )
    assert create_response.status_code == 200

    response = client.get("/chaos-fixed")
    assert response.status_code == 200
    assert sleep_calls == [0.12]


def test_stub_with_jitter_uses_random_range(client: TestClient, monkeypatch):
    sleep_calls: list[float] = []
    randint_args: list[tuple[int, int]] = []

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    def fake_randint(low: int, high: int) -> int:
        randint_args.append((low, high))
        return 137

    monkeypatch.setattr(core_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(core_module.random, "randint", fake_randint)

    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-jitter", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
            "chaos": {"latency": {"base_ms": 100, "jitter_ms": 50}},
        },
    )
    assert create_response.status_code == 200

    response = client.get("/chaos-jitter")
    assert response.status_code == 200
    assert randint_args == [(100, 150)]
    assert sleep_calls == [0.137]


def test_sse_chaos_applies_before_stream_open_only(client: TestClient, monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    monkeypatch.setattr(core_module.asyncio, "sleep", fake_sleep)

    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-sse", "method": "GET"},
            "action": {
                "sse": {
                    "default_delay_ms": 0,
                    "events": [{"id": "1", "event": "message", "data": "x"}],
                }
            },
            "chaos": {"latency": {"base_ms": 70, "jitter_ms": 0}},
        },
    )
    assert create_response.status_code == 200

    response = client.get("/chaos-sse")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert sleep_calls == [0.07]


def test_chaos_payload_rejects_negative_delay_or_jitter(client: TestClient):
    response_negative_delay = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-negative-delay", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
            "chaos": {"latency": {"base_ms": -1, "jitter_ms": 0}},
        },
    )
    assert response_negative_delay.status_code == 422

    response_negative_jitter = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-negative-jitter", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
            "chaos": {"latency": {"base_ms": 0, "jitter_ms": -1}},
        },
    )
    assert response_negative_jitter.status_code == 422


def test_chaos_payload_accepts_legacy_jitter_field_without_explicit_delay(
    client: TestClient,
):
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-missing-delay", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
            "chaos": {"jitter_ms": 5},
        },
    )

    assert response.status_code == 200


def test_chaos_payload_accepts_nested_connection_drop(client: TestClient):
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-drop-nested", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
            "chaos": {
                "faults": {
                    "connection_drop": {"probability": 0.5},
                }
            },
        },
    )

    assert response.status_code == 200


def test_chaos_payload_rejects_invalid_connection_drop_probability(client: TestClient):
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-drop-invalid", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
            "chaos": {
                "faults": {
                    "connection_drop": {"probability": 1.5},
                }
            },
        },
    )

    assert response.status_code == 422


def test_chaos_payload_rejects_top_level_connection_drop_key(client: TestClient):
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/chaos-drop-top-level", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "ok",
                }
            },
            "chaos": {"connection_drop": {"probability": 1.0}},
        },
    )

    assert response.status_code == 422
    assert "chaos.faults.connection_drop" in response.text


def test_should_drop_connection_uses_probability_threshold(monkeypatch):
    stub = core_module.Stub(
        request=core_module.StubRequest(path="/drop-threshold"),
        action=core_module.StubAction(
            response=core_module.StubResponse(status_code=200, headers={}, body="ok")
        ),
        chaos=core_module.StubChaos(
            faults=core_module.StubFaults(
                connection_drop=core_module.StubConnectionDrop(probability=0.5)
            )
        ),
    )

    monkeypatch.setattr(core_module.random, "random", lambda: 0.49)
    assert core_module.should_drop_connection(stub) is True

    monkeypatch.setattr(core_module.random, "random", lambda: 0.5)
    assert core_module.should_drop_connection(stub) is False
