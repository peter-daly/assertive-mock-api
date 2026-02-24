import pytest
from fastapi.testclient import TestClient

from assertive_mock_api_server.app import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_stub(
    client: TestClient,
    *,
    path: str,
    body: str,
    headers: dict | None = None,
) -> None:
    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": path},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": body,
                }
            },
        },
        headers=headers or {},
    )
    assert response.status_code == 200


def test_create_scope_and_duplicate_returns_conflict(client: TestClient):
    first = client.post("/__mock__/scopes", json={"name": "team_a"})
    second = client.post("/__mock__/scopes", json={"name": "team_a"})

    assert first.status_code == 201
    assert first.json()["name"] == "team_a"
    assert second.status_code == 409


def test_delete_scope_not_found(client: TestClient):
    response = client.delete("/__mock__/scopes/missing")

    assert response.status_code == 404


def test_ambiguous_scope_headers_return_400(client: TestClient):
    client.post("/__mock__/scopes", json={"name": "alpha"})
    client.post("/__mock__/scopes", json={"name": "beta"})

    response = client.post(
        "/__mock__/stubs",
        json={
            "request": {"path": "/ambiguous"},
            "action": {
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": "x",
                }
            },
        },
        headers={"alpha": "1", "beta": "2"},
    )

    assert response.status_code == 400


def test_scoped_matching_and_global_fallback(client: TestClient):
    client.post("/__mock__/scopes", json={"name": "team_a"})

    create_stub(client, path="/hello", body="global")

    scoped_before = client.get("/hello", headers={"team_a": "1"})
    assert scoped_before.status_code == 200
    assert scoped_before.text == "global"

    create_stub(client, path="/hello", body="scoped", headers={"team_a": "1"})

    scoped_after = client.get("/hello", headers={"team_a": "1"})
    unscoped = client.get("/hello")

    assert scoped_after.status_code == 200
    assert scoped_after.text == "scoped"
    assert unscoped.status_code == 200
    assert unscoped.text == "global"


def test_scoped_assertions_include_global_and_unscoped_assertions_exclude_scoped(
    client: TestClient,
):
    client.post("/__mock__/scopes", json={"name": "team_a"})

    # Global request should be visible to scoped assertions.
    client.get("/seen-global")
    scoped_assert = client.post(
        "/__mock__/assert",
        json={"path": "/seen-global"},
        headers={"team_a": "1"},
    )

    # Scoped request should not be visible to unscoped assertions.
    client.get("/seen-scoped", headers={"team_a": "1"})
    unscoped_assert = client.post("/__mock__/assert", json={"path": "/seen-scoped"})

    assert scoped_assert.status_code == 200
    assert scoped_assert.json()["result"] is True
    assert unscoped_assert.status_code == 200
    assert unscoped_assert.json()["result"] is False


def test_scoped_list_endpoints_include_global(client: TestClient):
    client.post("/__mock__/scopes", json={"name": "team_a"})

    create_stub(client, path="/list", body="global")
    create_stub(client, path="/list", body="scoped", headers={"team_a": "1"})

    stubs_unscoped = client.get("/__mock__/stubs")
    stubs_scoped = client.get("/__mock__/stubs", headers={"team_a": "1"})

    assert stubs_unscoped.status_code == 200
    assert len(stubs_unscoped.json()["stubs"]) == 1
    assert stubs_scoped.status_code == 200
    assert len(stubs_scoped.json()["stubs"]) == 2
    assert "stub_id" in stubs_scoped.json()["stubs"][0]
    assert stubs_scoped.json()["stubs"][0]["scope"] == "team_a"
    assert stubs_scoped.json()["stubs"][1]["scope"] is None

    client.get("/requests-only-global")
    client.get("/requests-scoped", headers={"team_a": "1"})

    requests_unscoped = client.get("/__mock__/requests")
    requests_scoped = client.get("/__mock__/requests", headers={"team_a": "1"})

    assert requests_unscoped.status_code == 200
    assert len(requests_unscoped.json()["requests"]) == 1
    assert requests_scoped.status_code == 200
    assert len(requests_scoped.json()["requests"]) == 2


def test_delete_scope_cascade_cleanup(client: TestClient):
    client.post("/__mock__/scopes", json={"name": "team_a"})

    create_stub(client, path="/cleanup", body="scoped", headers={"team_a": "1"})
    client.get("/cleanup", headers={"team_a": "1"})

    deleted = client.delete("/__mock__/scopes/team_a")
    recreated = client.post("/__mock__/scopes", json={"name": "team_a"})

    stubs = client.get("/__mock__/stubs", headers={"team_a": "1"})
    requests = client.get("/__mock__/requests", headers={"team_a": "1"})

    assert deleted.status_code == 200
    assert recreated.status_code == 201
    assert stubs.status_code == 200
    assert stubs.json()["stubs"] == []
    assert requests.status_code == 200
    assert requests.json()["requests"] == []


def test_delete_stub_endpoint_deletes_by_stub_id(client: TestClient):
    create_stub(client, path="/delete-me", body="x")
    list_response = client.get("/__mock__/stubs")

    assert list_response.status_code == 200
    stub_id = list_response.json()["stubs"][0]["stub_id"]

    delete_response = client.delete(f"/__mock__/stubs/{stub_id}")
    after_response = client.get("/delete-me")

    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True
    assert delete_response.json()["stub_id"] == stub_id
    assert after_response.status_code == 404


def test_delete_stub_endpoint_returns_404_when_missing(client: TestClient):
    response = client.delete("/__mock__/stubs/missing-id")
    assert response.status_code == 404


def test_list_scopes_endpoint_returns_scopes(client: TestClient):
    client.post("/__mock__/scopes", json={"name": "team_a"})
    client.post("/__mock__/scopes", json={"name": "team_b"})

    response = client.get("/__mock__/scopes")

    assert response.status_code == 200
    assert sorted(response.json()["scopes"]) == ["team_a", "team_b"]
