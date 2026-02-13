# Getting Started

## Run with Docker

```bash
docker compose up --build
```

Server base URL: `http://localhost:8910`

## Run locally

```bash
uv sync
uv run python -m assertive_mock_api_server
```

## Create your first stub

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H 'content-type: application/json' \
  -d '{
    "request": {
      "method": "GET",
      "path": "/health"
    },
    "action": {
      "response": {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "body": {"ok": true}
      }
    }
  }'
```

## Hit the mocked endpoint

```bash
curl -i http://localhost:8910/health
```

## Assert observed traffic

```bash
curl -X POST http://localhost:8910/__mock__/assert \
  -H 'content-type: application/json' \
  -d '{
    "method": "GET",
    "path": "/health",
    "times": {"equals": 1}
  }'
```

Expected:

```json
{"result": true}
```
