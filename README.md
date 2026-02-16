# Assertive Mock API Server

This is a mock API server that can be used to test your applications API calls.
While also leveraging the Assertive library to provide declarative assertions to your tests.

## Client Scope Context Manager

The client supports scoped setup/teardown via a context manager:

```python
from assertive_mock_api_client import MockApiClient

client = MockApiClient("http://localhost:8910")

with client.new_scope("team_a") as scoped:
    scoped.when_requested_with(path="/hello").respond_with(
        status_code=200,
        headers={},
        body="scoped response",
    )
    assert scoped.confirm_request(path="/hello")
```

Notes:
- On enter, the scope is created (`POST /__mock__/scopes`).
- On exit, the scope is deleted (`DELETE /__mock__/scopes/{name}`).
- Scoped client calls send the scope as a header key with value `"1"` by default.
- Nested scopes on the same root client are not supported.


<img width="3840" height="1062" alt="image" src="https://github.com/user-attachments/assets/c3045aee-5bca-4f06-87b5-3be9496d121d" />
