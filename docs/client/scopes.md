# Scoped Usage

Use `new_scope` to automatically create and tear down scopes.

```python
from assertive_mock_api_client import MockApiClient

client = MockApiClient("http://localhost:8910")

with client.new_scope("team-a") as scoped:
    scoped.when_requested_with(path="/checkout").respond_with(
        status_code=200,
        headers={},
        body="ok",
    )

    assert scoped.confirm_request(path="/checkout") is True
```

## Scoped JSON Response Example

```python
from assertive_mock_api_client import MockApiClient
import httpx

client = MockApiClient("http://localhost:8910")

with client.new_scope("team-a") as scoped:
    scoped.when_requested_with(path="/cart").respond_with_json(
        status_code=200,
        body={"items": [{"sku": "A1", "qty": 2}]},
    )

    response = httpx.get(
        "http://localhost:8910/cart",
        headers={"team-a": "1"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["sku"] == "A1"
```

## Notes

- On enter: client creates scope (`POST /__mock__/scopes`).
- On exit: client deletes scope (`DELETE /__mock__/scopes/{name}`).
- Scope header key is the scope name, value defaults to `"1"`.
- Nested scopes on a scoped client are disallowed.
- Parallel scopes from the root client are supported.

For production-style and multi-service concerns, see [Advanced Scopes](advanced-scopes.md).
