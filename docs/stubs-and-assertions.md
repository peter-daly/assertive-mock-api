# Stubs & Assertions

## Stub schema (`POST /__mock__/stubs`)

```json
{
  "request": {
    "method": "GET | {criteria}",
    "path": "/resource | {criteria}",
    "body": "... | {criteria}",
    "headers": {"...": "..."},
    "host": "localhost | {criteria}",
    "query": {"k": "v"}
  },
  "action": {
    "response": {
      "status_code": 200,
      "headers": {"content-type": "application/json"},
      "body": {"any": "json-compatible value"}
    },
    "proxy": {
      "url": "https://upstream.example/api",
      "headers": {"x-extra": "1"},
      "timeout": 5
    }
  },
  "max_calls": 1
}
```

Notes:

- `action.response` and `action.proxy` are mutually exclusive.
- `max_calls` limits how many times the stub can be matched.

## Assertion schema (`POST /__mock__/assert`)

```json
{
  "method": "GET | {criteria}",
  "path": "/resource | {criteria}",
  "headers": {"...": "..."},
  "body": "... | {criteria}",
  "host": "localhost | {criteria}",
  "query": {"k": "v"},
  "times": {"equals": 1}
}
```

`times` defaults to `>= 1` when omitted.

## Inspect state

- `GET /__mock__/stubs` returns configured stubs.
- `GET /__mock__/requests` returns captured requests.

These are useful for debugging failing test expectations.
