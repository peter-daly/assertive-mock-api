# Server API Usage

## Create a Stub

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"path": "/hello", "method": "GET"},
    "action": {
      "response": {
        "status_code": 200,
        "headers": {"Content-Type": "text/plain"},
        "body": "hello"
      }
    }
  }'
```

Path matcher note:
- String `request.path` values on stub creation support named path params using `{name}` segments.
- Example: `"/users/{id}"` matches `"/users/42"` and `"/users/alice"`.
- Path matching is exact-depth (same number of path segments).

## Confirm a Request Happened

```bash
curl -X POST http://localhost:8910/__mock__/assert \
  -H "Content-Type: application/json" \
  -d '{"path": "/hello", "method": "GET"}'
```

## Scoped Behavior

Create scope `team-a` and add a scoped stub by sending header key `team-a`.

```bash
curl -X POST http://localhost:8910/__mock__/scopes \
  -H "Content-Type: application/json" \
  -d '{"name": "team-a"}'

curl -X POST http://localhost:8910/__mock__/stubs \
  -H "Content-Type: application/json" \
  -H "team-a: 1" \
  -d '{
    "request": {"path": "/scoped"},
    "action": {"response": {"status_code": 200, "headers": {}, "body": "scoped"}}
  }'
```

Delete scope when done:

```bash
curl -X DELETE http://localhost:8910/__mock__/scopes/team-a
```

List scopes:

```bash
curl http://localhost:8910/__mock__/scopes
```

Delete a stub by `stub_id`:

```bash
curl -X DELETE http://localhost:8910/__mock__/stubs/<stub-id>
```

## Chaos Latency (Delay + Jitter)

You can define per-stub request latency using top-level `chaos` config.

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"path": "/chaos", "method": "GET"},
    "action": {
      "response": {
        "status_code": 200,
        "headers": {},
        "body": "slow"
      }
    },
    "chaos": {
      "latency": {
        "base_ms": 100,
        "jitter_ms": 50
      }
    }
  }'
```

Semantics:
- `chaos.latency.base_ms` defaults to `0`.
- `chaos.latency.jitter_ms` defaults to `0`.
- Actual delay is sampled from:
  - fixed `base_ms` when `jitter_ms = 0`
  - uniform range `[base_ms, base_ms + jitter_ms]` when jitter is set.
- Chaos applies across `response`, `proxy`, and `sse` action types.
- For SSE stubs, chaos delay is applied once before stream start; per-event SSE delays still use existing SSE fields.

## Templated Responses

Response body templates use an explicit `template_body` field.

Rules:
- `action.response.body` is always static/plain.
- `action.response.template_body` is rendered as a template.
- Exactly one of `body` or `template_body` must be provided.

Use request query values:

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"path": "/hello"},
    "action": {
      "response": {
        "status_code": 200,
        "headers": {"Content-Type": "text/plain"},
        "template_body": "Hello {{ request.query.name }}"
      }
    }
  }'

curl "http://localhost:8910/hello?name=Peter"
```

Use path params captured from path-pattern matching:

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"path": "/users/{id}", "method": "GET"},
    "action": {
      "response": {
        "status_code": 200,
        "headers": {"Content-Type": "text/plain"},
        "template_body": "user id: {{ request.path_params.id }}"
      }
    }
  }'

curl http://localhost:8910/users/u_123
```

For JSON requests, `request.body` is parsed JSON and can be accessed by field:

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"path": "/user"},
    "action": {
      "response": {
        "status_code": 200,
        "headers": {"Content-Type": "text/plain"},
        "template_body": "user id: {{ request.body.user.id }}"
      }
    }
  }'

curl -X POST http://localhost:8910/user \
  -H "Content-Type: application/json" \
  -d '{"user":{"id":"u_123"}}'
```

For non-JSON requests, `request.body` remains raw text/bytes.

If request `Content-Type` is JSON but the body is invalid JSON, the server returns:
- HTTP `500`
- JSON payload with `error: "TEMPLATE_RENDER_ERROR"`

If both `body` and `template_body` are set (or neither is set), stub creation is
rejected with a validation error (`422`).

## Mock SSE Responses

Use `action.sse` to stream Server-Sent Events.

Rules:
- `action.sse` is mutually exclusive with `action.response` and `action.proxy`.
- SSE responses always return status `200`.
- SSE headers are server-managed:
  - `Content-Type: text/event-stream`
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"path": "/events", "method": "GET"},
    "action": {
      "sse": {
        "default_delay_ms": 100,
        "events": [
          {"id": "1", "event": "message", "data": "first"},
          {"id": "2", "event": "message", "data": "second", "delay_ms": 250}
        ]
      }
    }
  }'
```

Consume the stream:

```bash
curl -N http://localhost:8910/events
```

Templating is supported in SSE string fields: `data`, `id`, and `event`.

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"path": "/events-template"},
    "action": {
      "sse": {
        "events": [
          {
            "id": "{{ request.query.id }}",
            "event": "room",
            "data": "room={{ request.query.room }}"
          }
        ]
      }
    }
  }'

curl -N "http://localhost:8910/events-template?room=blue&id=evt-9"
```

## Admin UI

The admin UI is available at:

```bash
http://localhost:8910/__admin__
```

Notes:
- This is an in-app operational UI for local/internal use.
- v1 has no auth.
- It uses HTMX polling to keep requests/stubs/scopes panels updated.

## More Matching Patterns

For detailed examples across path/method/header/query/body/scope and an explanation of how Assertive criteria are used under the hood, see [Matching Scenarios](matching-scenarios.md).

Assertion note:
- `POST /__mock__/assert` keeps Assertive criteria semantics for `path`.
- A string like `"/users/{id}"` is treated as a literal assertion path unless you send explicit criteria payloads.
