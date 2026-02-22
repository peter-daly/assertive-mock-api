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
