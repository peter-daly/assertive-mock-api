# Assertive Mock API Server

A docker-friendly mock API service for integration testing, built on FastAPI and the `assertive` criteria model.

## What it gives you

- A **catch-all HTTP mock endpoint** (`/{path:path}`) for any method.
- **Declarative request matching** with criteria on method/path/body/headers/query/host.
- **Programmable actions** per stub:
  - static response, or
  - proxy to an upstream service.
- **Request capture + assertions** so tests can verify outbound calls.

## Core flow

1. Register one or more stubs via `POST /__mock__/stubs`.
2. Run your application against the mock server.
3. Inspect requests via `GET /__mock__/requests`.
4. Assert expectations via `POST /__mock__/assert`.

## Endpoints

### Management

- `POST /__mock__/stubs`
- `GET /__mock__/stubs`
- `GET /__mock__/requests`
- `POST /__mock__/assert`

### Runtime matching

- `/{path:path}` (all standard HTTP methods)

If no stub matches a request, server responds with `404` and `NO_STUB_MATCH_FOUND`.

## Start quickly

```bash
docker compose up --build
```

Then open `http://localhost:8910/docs`.

For more detailed examples, continue to [Getting Started](getting-started.md) and [Stubs & Assertions](stubs-and-assertions.md).
