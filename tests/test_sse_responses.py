import pytest
from fastapi.testclient import TestClient

from assertive_mock_api_server.app import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_sse_stub_streams_events_in_order(client: TestClient):
    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/events", "method": "GET"},
            "action": {
                "sse": {
                    "default_delay_ms": 0,
                    "events": [
                        {"id": "1", "event": "message", "data": "first"},
                        {"id": "2", "event": "message", "data": "second"},
                    ],
                }
            },
        },
    )
    assert create_response.status_code == 200

    response = client.get("/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.text == (
        "id: 1\nevent: message\ndata: first\n\nid: 2\nevent: message\ndata: second\n\n"
    )


def test_sse_event_templates_render_from_request_context(client: TestClient):
    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/events-template", "method": "GET"},
            "action": {
                "sse": {
                    "events": [
                        {
                            "id": "{{ request.query.id }}",
                            "event": "room",
                            "data": "room={{ request.query.room }}",
                        }
                    ]
                }
            },
        },
    )
    assert create_response.status_code == 200

    response = client.get("/events-template", params={"room": "blue", "id": "evt-9"})

    assert response.status_code == 200
    assert response.text == "id: evt-9\nevent: room\ndata: room=blue\n\n"


def test_sse_template_error_returns_500(client: TestClient):
    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/events-error", "method": "POST"},
            "action": {
                "sse": {
                    "events": [{"data": "{{ request.body.user.id }}"}],
                }
            },
        },
    )
    assert create_response.status_code == 200

    response = client.post(
        "/events-error",
        content='{"user":',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 500
    assert response.json()["error"] == "TEMPLATE_RENDER_ERROR"


def test_sse_payload_validation_rejects_empty_events(client: TestClient):
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/events-empty"},
            "action": {"sse": {"events": []}},
        },
    )

    assert response.status_code == 422


def test_sse_payload_validation_rejects_negative_timing_values(client: TestClient):
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/events-negative"},
            "action": {
                "sse": {
                    "default_delay_ms": -1,
                    "events": [{"data": "x", "retry": -5, "delay_ms": -3}],
                }
            },
        },
    )

    assert response.status_code == 422


def test_sse_payload_validation_rejects_multiple_action_types(client: TestClient):
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/events-multi"},
            "action": {
                "response": {"status_code": 200, "headers": {}, "body": "ok"},
                "sse": {"events": [{"data": "x"}]},
            },
        },
    )

    assert response.status_code == 422
