# Docker Compose Deploy

Use this compose file to run the server on port `8910`.

```yaml
services:
  assertive-mock-api-server:
    image: ghcr.io/peter-daly/assertive-mock-api/server:latest
    ports:
      - "8910:8910"
```

## Start

```bash
docker compose up
```

## Health Check

```bash
curl http://localhost:8910/__mock__
```

Expected response contains available mock endpoints.
