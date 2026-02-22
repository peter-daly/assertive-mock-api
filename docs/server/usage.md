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

## More Matching Patterns

For detailed examples across path/method/header/query/body/scope and an explanation of how Assertive criteria are used under the hood, see [Matching Scenarios](matching-scenarios.md).
