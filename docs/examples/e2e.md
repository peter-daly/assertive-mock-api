# End-to-End Example

This page shows both unscoped and scoped end-to-end flows.

## Unscoped Flow

```python
from assertive_mock_api_client import MockApiClient
import httpx

client = MockApiClient("http://localhost:8910")

client.when_requested_with(path="/payment", method="POST").respond_with_json(
    status_code=200,
    body={"status": "accepted"},
)

response = httpx.post("http://localhost:8910/payment", json={"amount": 42})

assert response.status_code == 200
assert response.json()["status"] == "accepted"
assert client.confirm_request(path="/payment", method="POST") is True
```

```mermaid
sequenceDiagram
  participant T as Test
  participant C as MockApiClient
  participant S as Mock Server
  participant A as App Request

  T->>C: create global stub
  C->>S: POST /__mock__/stubs
  A->>S: POST /payment
  S-->>A: 200 {status: accepted}
  T->>C: confirm_request(...)
  C->>S: POST /__mock__/assert
```

## Scoped Flow

```python
from assertive_mock_api_client import MockApiClient
import httpx

client = MockApiClient("http://localhost:8910")

with client.new_scope("payment-suite") as scoped:
    scoped.when_requested_with(path="/payment", method="POST").respond_with_json(
        status_code=200,
        body={"status": "accepted"},
    )

    response = httpx.post(
        "http://localhost:8910/payment",
        headers={"payment-suite": "1"},
        json={"amount": 42},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert scoped.confirm_request(path="/payment", method="POST") is True
```

```mermaid
sequenceDiagram
  participant T as Test
  participant C as MockApiClient
  participant S as Mock Server
  participant A as App Request

  T->>C: new_scope("payment-suite")
  C->>S: POST /__mock__/scopes
  T->>C: create scoped stub
  C->>S: POST /__mock__/stubs (header key payment-suite)
  A->>S: POST /payment (header key payment-suite)
  S-->>A: 200 {status: accepted}
  T->>C: confirm_request(...)
  C->>S: POST /__mock__/assert (header key payment-suite)
  T->>C: context exit
  C->>S: DELETE /__mock__/scopes/payment-suite
```
