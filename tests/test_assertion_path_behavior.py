import pytest
from fastapi.testclient import TestClient

from assertive_mock_api_server.app import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_assertion_path_string_does_not_use_stub_path_parameter_matching(client: TestClient):
    client.get("/users/42")

    response = client.post("/__mock__/assert", json={"path": "/users/{id}"})

    assert response.status_code == 200
    assert response.json()["result"] is False
