# Client Overview

`MockApiClient` is the Python helper for creating stubs and validating requests.

## Install

```bash
pip install assertive-mock-api-client
```

## Basic Usage

```python
from assertive_mock_api_client import MockApiClient

client = MockApiClient("http://localhost:8910")

client.when_requested_with(path="/hello", method="GET").respond_with(
    status_code=200,
    headers={"Content-Type": "text/plain"},
    body="hello",
)

assert client.confirm_request(path="/hello", method="GET") is True
```

## Criteria Objects Auto-Serialize

You can pass Assertive `Criteria` objects directly in client calls. The client
automatically serializes them to API-safe JSON.

```python
from assertive_mock_api_client import MockApiClient
from assertive import between

client = MockApiClient("http://localhost:8910")

assert client.confirm_request(path="/hello", times=between(1, 3)) is True
```

Equivalent serialized payload conceptually includes:

```json
{
  "times": {"$between": {"lower": 1, "upper": 3, "is_inclusive": true}}
}
```

`between(1, 3).exclusive()` serializes the same shape with `"is_inclusive": false`.

## Returning JSON

Use `respond_with_json` to return a JSON body with the correct content type.

```python
from assertive_mock_api_client import MockApiClient
import httpx

client = MockApiClient("http://localhost:8910")

client.when_requested_with(path="/orders/123", method="GET").respond_with_json(
    status_code=200,
    body={"id": "123", "status": "shipped"},
)

response = httpx.get("http://localhost:8910/orders/123")

assert response.status_code == 200
assert response.json()["status"] == "shipped"
```

## Mocking SSE

Use `respond_with_sse` to create a streaming SSE stub.

```python
from assertive_mock_api_client import MockApiClient
import httpx

client = MockApiClient("http://localhost:8910")

client.when_requested_with(path="/events", method="GET").respond_with_sse(
    default_delay_ms=100,
    events=[
        {"id": "1", "event": "message", "data": "first"},
        {"id": "2", "event": "message", "data": "second", "delay_ms": 250},
    ],
)

with httpx.stream("GET", "http://localhost:8910/events") as response:
    assert response.status_code == 200
    for line in response.iter_lines():
        if line:
            print(line)
```

## Chaos Connection Drop

Use `with_connection_drop(probability=...)` to inject connection-drop faults.

```python
from assertive_mock_api_client import MockApiClient
import httpx

client = MockApiClient("http://localhost:8910")

client.when_requested_with(path="/unstable", method="GET").with_connection_drop(
    probability=1.0
).respond_with(
    status_code=200,
    headers={"Content-Type": "text/plain"},
    body="possibly dropped",
)

with httpx.Client() as http_client:
    try:
        http_client.get("http://localhost:8910/unstable")
        raise AssertionError("Expected a transport/protocol error")
    except httpx.HTTPError:
        pass
```

`with_latency(...)` and `with_connection_drop(...)` can be chained together; the
client emits both `chaos.latency` and `chaos.faults.connection_drop`.
`with_delay(...)` remains as a backward-compatible deprecated alias.
