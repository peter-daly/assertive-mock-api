import pytest
from fastapi.testclient import TestClient

from assertive_mock_api_server.app import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_admin_index_renders_html_shell(client: TestClient):
    response = client.get("/__admin__")

    assert response.status_code == 200
    assert "Assertive Mock API Admin" in response.text
    assert 'id="stubs-panel"' in response.text
    assert "htmx.org" in response.text


def test_admin_partials_render(client: TestClient):
    stubs = client.get("/__admin__/partials/stubs")
    requests = client.get("/__admin__/partials/requests")
    scopes = client.get("/__admin__/partials/scopes")

    assert stubs.status_code == 200
    assert "Create New Stub" in stubs.text
    assert requests.status_code == 200
    assert "Requests (latest 100)" in requests.text
    assert scopes.status_code == 200
    assert "Scopes" in scopes.text


def test_admin_new_stub_page_renders(client: TestClient):
    response = client.get("/__admin__/stubs/new")

    assert response.status_code == 200
    assert "Create a Stub" in response.text
    assert "1. Match" in response.text
    assert "Create Stub" in response.text
    assert "/__mock__/stubs" in response.text
    assert "Common headers" in response.text
    assert "Content-Type: application/json" in response.text
    assert 'data-target-textarea="ui-request-headers"' in response.text
    assert 'data-target-textarea="ui-response-headers"' in response.text
    assert 'data-target-textarea="ui-proxy-headers"' in response.text
    assert 'id="ui-chaos-delay-ms"' in response.text
    assert 'id="ui-chaos-jitter-ms"' in response.text
    assert "Chaos latency is sampled from" in response.text


def test_admin_stub_detail_page_renders(client: TestClient):
    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/stub-detail", "method": "GET"},
            "action": {"response": {"status_code": 200, "headers": {}, "body": "x"}},
            "chaos": {"latency": {"base_ms": 100, "jitter_ms": 25}},
        },
    )
    assert create_response.status_code == 200

    stubs_response = client.get("/__mock__/stubs")
    stub_id = stubs_response.json()["stubs"][0]["stub_id"]

    detail_response = client.get(f"/__admin__/stubs/{stub_id}")
    assert detail_response.status_code == 200
    assert "Stub Detail" in detail_response.text
    assert stub_id in detail_response.text
    assert "/stub-detail" in detail_response.text
    assert "Chaos" in detail_response.text
    assert '"base_ms": 100' in detail_response.text
    assert '"jitter_ms": 25' in detail_response.text


def test_admin_stub_detail_page_returns_404_for_missing_stub(client: TestClient):
    response = client.get("/__admin__/stubs/missing-stub-id")
    assert response.status_code == 404


def test_admin_scope_detail_page_renders(client: TestClient):
    create_scope_response = client.post(
        "/__mock__/scopes", json={"name": "team_detail"}
    )
    assert create_scope_response.status_code == 201

    create_stub_response = client.post(
        "/__mock__/stubs",
        headers={"team_detail": "1"},
        json={
            "request": {"path": "/scope-detail", "method": "GET"},
            "action": {"response": {"status_code": 200, "headers": {}, "body": "ok"}},
        },
    )
    assert create_stub_response.status_code == 200

    call_response = client.get("/scope-detail", headers={"team_detail": "1"})
    assert call_response.status_code == 200

    detail_response = client.get("/__admin__/scopes/team_detail")
    assert detail_response.status_code == 200
    assert "Scope Detail" in detail_response.text
    assert "team_detail" in detail_response.text
    assert "/scope-detail" in detail_response.text


def test_admin_scope_detail_page_returns_404_for_missing_scope(client: TestClient):
    response = client.get("/__admin__/scopes/missing_scope")
    assert response.status_code == 404


def test_admin_create_scope_and_delete_scope(client: TestClient):
    create_response = client.post("/__mock__/scopes", json={"name": "team_x"})

    assert create_response.status_code == 201
    assert create_response.json()["name"] == "team_x"

    delete_response = client.delete("/__admin__/actions/scopes/team_x")

    assert delete_response.status_code == 200
    assert "team_x" not in delete_response.text


def test_admin_create_stub_response_and_delete(client: TestClient):
    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {
                "path": "/admin-hello",
                "method": "GET",
                "headers": {"X-Team": "qa"},
                "query": {"q": "hello"},
            },
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {"Content-Type": "text/plain"},
                    "body": "hello-admin",
                }
            },
            "chaos": {"latency": {"base_ms": 0, "jitter_ms": 0}},
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["success"] is True

    stubs_response = client.get("/__mock__/stubs")
    stub_id = stubs_response.json()["stubs"][0]["stub_id"]

    delete_response = client.delete(f"/__admin__/actions/stubs/{stub_id}")
    assert delete_response.status_code == 200

    after_response = client.get("/admin-hello")
    assert after_response.status_code == 404


def test_admin_create_stub_sse_action(client: TestClient):
    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {
                "path": "/admin-events",
                "method": "GET",
            },
            "action": {
                "sse": {
                    "default_delay_ms": 0,
                    "events": [{"id": "1", "event": "message", "data": "x"}],
                }
            },
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["success"] is True

    stream_response = client.get("/admin-events")
    assert stream_response.status_code == 200
    assert stream_response.headers["content-type"].startswith("text/event-stream")


def test_admin_create_stub_validation_error_renders_422(client: TestClient):
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/invalid", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "x",
                    "template_body": "hello {{ request.path }}",
                }
            },
        },
    )

    assert response.status_code == 422
    assert "Exactly one of body or template_body must be provided" in response.text


def test_admin_requests_partial_shows_matched_stub_id(client: TestClient):
    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/matched-admin", "method": "GET"},
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

    stubs_response = client.get("/__mock__/stubs")
    stub_id = stubs_response.json()["stubs"][0]["stub_id"]

    matched_call = client.get("/matched-admin")
    assert matched_call.status_code == 200

    unmatched_call = client.get("/not-matched-admin")
    assert unmatched_call.status_code == 404

    requests_partial = client.get("/__admin__/partials/requests")
    assert requests_partial.status_code == 200
    assert "Matched Stub ID" in requests_partial.text
    assert stub_id in requests_partial.text
