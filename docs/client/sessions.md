# Session Usage

Use `new_session` to automatically delete stubs created within a context. This is
useful for ensuring test isolation without needing to create separate named scopes.

```python
from assertive_mock_api_client import MockApiClient

client = MockApiClient("http://localhost:8910")

with client.new_session() as session:
    session.when_requested_with(path="/hello").respond_with(
        status_code=200,
        headers={"Content-Type": "text/plain"},
        body="hi",
    )
    
    # Stub is active and will be used for matching
    ...

# Stub is deleted automatically here when the context exits
```

## How It Works

Unlike `new_scope`, which creates a named grouping on the server and relies on
header-based routing, `new_session` operates by tracking individual stubs.

This means sessions work within whatever scope the client is currently using
(including the default scope).

## Notes

- **Isolation:** Ideal for cleaning up stubs in tests where you want to ensure
  no leaked state remains for the next test case.
- **Nesting:** Nested sessions on the same client instance are disallowed.
- **Interactions:** You cannot start a `new_scope` from within a `new_session`.
  However, you can start a `new_session` from within a `new_scope`.
