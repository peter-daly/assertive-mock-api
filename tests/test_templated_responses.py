import pytest
from fastapi.testclient import TestClient
from httpx import Response

from assertive_mock_api_server.app import app

_UNSET = object()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_stub(
    client: TestClient,
    *,
    path: str,
    method: str | None,
    body: object = _UNSET,
    template_body: object = _UNSET,
) -> Response:
    request_payload = {"path": path}
    if method is not None:
        request_payload["method"] = method

    response_payload = {"status_code": 200, "headers": {}}
    if body is not _UNSET:
        response_payload["body"] = body
    if template_body is not _UNSET:
        response_payload["template_body"] = template_body

    response = client.post(
        "/__mock__/stubs",
        json={
            "request": request_payload,
            "action": {"response": response_payload},
        },
    )
    return response


def test_templated_response_renders_from_query(client: TestClient):
    create_response = create_stub(
        client,
        path="/hello",
        method="GET",
        template_body="Hello {{ request.query.name }}",
    )
    assert create_response.status_code == 200

    response = client.get("/hello", params={"name": "Peter"})

    assert response.status_code == 200
    assert response.text == "Hello Peter"


def test_templated_response_renders_from_path_params(client: TestClient):
    create_response = create_stub(
        client,
        path="/users/{id}",
        method="GET",
        template_body="id={{ request.path_params.id }}",
    )
    assert create_response.status_code == 200

    response = client.get("/users/u_9")

    assert response.status_code == 200
    assert response.text == "id=u_9"


def test_templated_response_renders_from_json_request_body(client: TestClient):
    create_response = create_stub(
        client,
        path="/user",
        method="POST",
        template_body="id={{ request.body.user.id }}",
    )
    assert create_response.status_code == 200

    response = client.post("/user", json={"user": {"id": "u_7"}})

    assert response.status_code == 200
    assert response.text == "id=u_7"


def test_template_body_can_return_json_object(client: TestClient):
    create_response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/json-template", "method": "GET"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {"Content-Type": "application/json"},
                    "template_body": '{"id":"{{ request.query.id }}","ok":true}',
                }
            },
        },
    )
    assert create_response.status_code == 200

    response = client.get("/json-template", params={"id": "abc-123"})

    assert response.status_code == 200
    assert response.json() == {"id": "abc-123", "ok": True}


def test_invalid_json_body_for_json_content_type_returns_template_error(
    client: TestClient,
):
    create_response = create_stub(
        client,
        path="/broken",
        method="POST",
        template_body="{{ request.body.user.id }}",
    )
    assert create_response.status_code == 200

    response = client.post(
        "/broken",
        content='{"user":',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 500
    assert response.json()["error"] == "TEMPLATE_RENDER_ERROR"
    assert (
        response.json()["detail"] == "Invalid JSON request body for JSON content-type"
    )


def test_non_templated_string_body_keeps_existing_behavior(client: TestClient):
    create_response = create_stub(
        client,
        path="/static",
        method="GET",
        body="static-response",
    )
    assert create_response.status_code == 200

    response = client.get("/static")

    assert response.status_code == 200
    assert response.text == "static-response"


def test_static_response_can_return_json_body(client: TestClient):
    create_response = create_stub(
        client,
        path="/json-static",
        method="GET",
        body={"ok": True, "items": [1, 2], "meta": {"source": "stub"}},
    )
    assert create_response.status_code == 200

    response = client.get("/json-static")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "items": [1, 2],
        "meta": {"source": "stub"},
    }


def test_plain_body_with_template_markers_is_literal(client: TestClient):
    create_response = create_stub(
        client,
        path="/literal",
        method="GET",
        body="hello {{ request.query.name }}",
    )
    assert create_response.status_code == 200

    response = client.get("/literal", params={"name": "Peter"})

    assert response.status_code == 200
    assert response.text == "hello {{ request.query.name }}"


def test_non_string_response_body_is_not_templated(client: TestClient):
    create_response = create_stub(
        client,
        path="/json",
        method="GET",
        body={"message": "{{ request.query.name }}"},
    )
    assert create_response.status_code == 200

    response = client.get("/json", params={"name": "Peter"})

    assert response.status_code == 200
    assert response.json()["message"] == "{{ request.query.name }}"


def test_stub_rejects_when_body_and_template_body_are_both_set(client: TestClient):
    response = create_stub(
        client,
        path="/invalid-both",
        method="GET",
        body="x",
        template_body="{{ request.query.name }}",
    )

    assert response.status_code == 422


def test_stub_rejects_when_neither_body_nor_template_body_is_set(client: TestClient):
    response = create_stub(
        client,
        path="/invalid-neither",
        method="GET",
        body=_UNSET,
        template_body=_UNSET,
    )

    assert response.status_code == 422
