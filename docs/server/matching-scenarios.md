# Matching Scenarios

This page shows practical matching patterns and explains how matching is powered by Assertive criteria under the hood.

## How Matching Works Internally

When you send `request` or `assert` payloads to the server:

- For stub creation (`POST /__mock__/stubs`), string `request.path` values are handled by the server path-pattern matcher (`/users/{id}` style).
- For assertions (`POST /__mock__/assert`), string values are converted to Assertive criteria via `ensure_criteria(...)`.
- Dict values are deserialized using `assertive.serialize.deserialize(...)`.
- Plain dicts for `headers` and `query` are converted with `has_key_values(...)`.

In server code this happens in `payloads.py` through:

- `ensure_str_criteria(...)`
- `ensure_dict_criteria(...)`
- `StubRequestPayload.to_stub_request()`
- `ApiAssertionPayload.to_api_assertion()`

So matching is not simple string equality only:
- Stubs use path-pattern matching for string paths plus Assertive criteria for other fields.
- Assertions continue to use Assertive criteria evaluation.

## Scenario 1: Exact Path + Method

```python
from assertive_mock_api_client import MockApiClient

client = MockApiClient("http://localhost:8910")

client.when_requested_with(path="/health", method="GET").respond_with(
    status_code=200,
    headers={},
    body="ok",
)
```

This creates criteria equivalent to Assertive equality checks for both fields.

## Scenario 1b: Path Parameters

```python
client.when_requested_with(path="/users/{id}", method="GET").respond_with_template(
    status_code=200,
    headers={},
    template_body="id={{ request.path_params.id }}",
)
```

This matches `/users/42`, `/users/u_7`, etc. Captured values are available as `request.path_params`.

## Scenario 2: Header Subset Match

```python
client.when_requested_with(
    path="/orders",
    headers={"x-tenant": "acme"},
).respond_with(status_code=200, headers={}, body="tenant matched")
```

Header/query dict matching uses key-value criteria (`has_key_values`).
Additional keys can still exist on the incoming request.

## Scenario 3: Query Match

```python
client.when_requested_with(
    path="/search",
    query={"q": "book", "limit": "10"},
).respond_with_json(status_code=200, body={"results": []})
```

## Scenario 4: JSON Body Match

```python
client.when_requested_with(
    path="/checkout",
    json={"cart_id": "c-1", "currency": "USD"},
).respond_with_json(status_code=200, body={"accepted": True})
```

Using `json=...` produces Assertive JSON matching criteria via `as_json_matches(...)`.

## Scenario 5: Host Match

```python
client.when_requested_with(
    host="payments.internal",
    path="/charge",
).respond_with(status_code=200, headers={}, body="routed")
```

Useful when your app calls the same mock server from different virtual hosts.

## Scenario 6: Broad Fallback Stub

```python
client.when_requested_with(path="/users").respond_with(
    status_code=200,
    headers={},
    body="fallback",
)

client.when_requested_with(path="/users", method="GET").respond_with(
    status_code=200,
    headers={},
    body="specific",
)
```

The server picks the strongest match (more matched fields).

## Scenario 7: Max Calls

```python
client.when_requested_with(path="/one-time").respond_with(
    status_code=200,
    headers={},
    body="once",
    max_calls=1,
)
```

After one match, this stub no longer matches.

## Scenario 8: Scoped + Global Matching

```python
with client.new_scope("suite-a") as scoped:
    # Scoped stub
    scoped.when_requested_with(path="/profile").respond_with(
        status_code=200, headers={}, body="suite-a"
    )

# Global fallback
client.when_requested_with(path="/profile").respond_with(
    status_code=200, headers={}, body="global"
)
```

For a request carrying header key `suite-a`, scoped stubs are checked first, then global.

## Scenario 9: Request Assertions

```python
assert client.confirm_request(path="/health", method="GET") is True
```

Assertions also use Assertive criteria through `ApiAssertionPayload -> ApiAssertion` conversion.

Important: assertion `path` strings are not path-pattern strings. A payload such as
`{"path": "/users/{id}"}` checks for that literal path string unless you use explicit criteria objects.

## Scenario 10: Times Assertions

```python
from assertive import is_gte

assert client.confirm_request(path="/health", times=is_gte(2)) is True
```

`times` is an Assertive criterion, not only an integer equality.

## Advanced: Sending Raw Assertive Criteria

Server endpoints accept serialized criteria dicts (deserialized internally). The recommended way is to build them through the Python client (`serialize(...)` is already integrated), but direct API users can also send criteria-shaped payloads.

If you are using raw HTTP payloads, keep the format consistent with Assertive serialized criteria objects.
