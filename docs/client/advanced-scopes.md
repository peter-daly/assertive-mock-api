# Advanced Scopes

Scopes are powerful, but they only work when the scope header reaches the mock server.

## Critical Requirement: Header Propagation

If your test creates a scope named `checkout-flow`, requests sent by your system under test must include a header key named `checkout-flow` when calling the mock server.

The header value is not important for scope selection. Only the header key matters.

```text
Header key: checkout-flow
Header value: any value (client defaults to "1")
```

If this header is not propagated end-to-end, the server treats the request as unscoped and your scoped stubs/assertions may appear to fail.

## What to Verify in Your System Under Test

1. Your inbound request context captures the scope identifier.
2. Outbound HTTP client code forwards that scope as a header key.
3. Proxies, gateways, middleware, and service meshes do not strip that header.
4. Retries/background jobs preserve the same scope header.

## Common Failure Modes

### Scoped stub not matched

Symptom: request returns global fallback or `NO_STUB_MATCH_FOUND`.

Likely cause: outbound call from the system under test did not include the scope header key.

### Assertion unexpectedly false

Symptom: `confirm_request(...)` in a scoped client returns `False`.

Likely cause: request logged as global because no scope header key reached the server.

### Ambiguous scope resolution (`400`)

Symptom: mock control endpoints or request handling fail with `400`.

Likely cause: request contains multiple header keys that match different existing scopes.

## Debugging Checklist

- Call `GET /__mock__/requests` with your scope header and confirm entries have expected `scope`.
- Call `GET /__mock__/stubs` with your scope header and ensure scoped stubs are present.
- Inspect actual outbound HTTP headers from your system under test (not just test setup code).
- Add a temporary middleware/log statement to print outgoing header keys.

## Minimal Pattern

```python
from assertive_mock_api_client import MockApiClient
import httpx

client = MockApiClient("http://localhost:8910")

with client.new_scope("checkout-flow") as scoped:
    scoped.when_requested_with(path="/payment").respond_with(
        status_code=200,
        headers={},
        body="ok",
    )

    # Simulate the system under test call - must forward scope header key
    response = httpx.post(
        "http://localhost:8910/payment",
        headers={"checkout-flow": "trace-123"},
    )

    assert response.status_code == 200
    assert scoped.confirm_request(path="/payment") is True
```
