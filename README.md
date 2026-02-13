# Assertive Mock API Server

`assertive-mock-api-server` is a lightweight HTTP mock server built with FastAPI and powered by the [`assertive`](https://pypi.org/project/assertive/) criteria model.

It is designed for integration and end-to-end tests where you need to:

- stand up a disposable mock API quickly,
- define request stubs declaratively,
- optionally proxy requests to real upstream services, and
- assert what traffic your application made.

## Highlights

- **Catch-all mock endpoint**: any route/method can be mocked.
- **Declarative matching**: match on method, path, query params, headers, body, and host.
- **Stub actions**:
  - return a static response, or
  - proxy to an upstream URL.
- **Request log + assertions**: verify requests were received with criteria and cardinality.
- **Docker-first**: ships with a production-ready image entrypoint.

## Run with Docker

Build and run:

```bash
docker compose up --build
```

The server listens on `http://localhost:8910`.

## Run locally (Python)

```bash
uv sync
uv run python -m assertive_mock_api_server
```

Or using Uvicorn directly:

```bash
uv run uvicorn assertive_mock_api_server.app:app --host 0.0.0.0 --port 8910
```

## API overview

### Management endpoints

These endpoints configure and inspect mock behavior:

- `POST /__mock__/stubs` — add a stub.
- `GET /__mock__/stubs` — list configured stubs.
- `GET /__mock__/requests` — list captured requests.
- `POST /__mock__/assert` — run assertions against captured requests.

### Catch-all endpoint

All non-`/__mock__/*` routes are handled by a catch-all handler and matched against registered stubs.
If no stub matches, the server returns:

- status: `404`
- body: `NO_STUB_MATCH_FOUND`

## Quick start example

### 1) Register a stub

```bash
curl -X POST http://localhost:8910/__mock__/stubs \
  -H 'content-type: application/json' \
  -d '{
    "request": {
      "method": "GET",
      "path": "/users/42"
    },
    "action": {
      "response": {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "body": {"id": 42, "name": "Ada"}
      }
    }
  }'
```

### 2) Call the mocked route

```bash
curl -i http://localhost:8910/users/42
```

### 3) Assert that it was called

```bash
curl -X POST http://localhost:8910/__mock__/assert \
  -H 'content-type: application/json' \
  -d '{
    "method": "GET",
    "path": "/users/42",
    "times": {"equals": 1}
  }'
```

Expected response:

```json
{"result": true}
```

## Stub payload reference

A stub payload sent to `POST /__mock__/stubs`:

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

`action.response` and `action.proxy` are **mutually exclusive**.

## Assertion payload reference

Payload for `POST /__mock__/assert`:

```json
{
  "method": "GET | {criteria}",
  "path": "/users/42 | {criteria}",
  "headers": {"...": "..."},
  "body": "... | {criteria}",
  "host": "localhost | {criteria}",
  "query": {"k": "v"},
  "times": {"equals": 1}
}
```

When omitted, `times` defaults to `>= 1`.

## OpenAPI docs

Interactive docs are available at:

- Swagger UI: `http://localhost:8910/docs`
- OpenAPI JSON: `http://localhost:8910/openapi.json`

## Development

```bash
make install-dev-deps
make ci
```

## License

MIT.
