# Server Overview

The server stores incoming traffic and serves stubbed responses.

## Core Concepts

- `Stub`: request matcher + action (`response` or `proxy`).
- `Scope`: optional isolation boundary using request header keys.
- `Global`: stubs/requests without scope.

Scoped requests include both scope-specific and global stubs.

```mermaid
flowchart TD
  Req[Incoming Request] --> Resolve[Resolve Scope From Header Keys]
  Resolve --> Match[Find Best Stub Match]
  Match -->|found| Resp[Return Stubbed Response]
  Match -->|none| NotFound[404 NO_STUB_MATCH_FOUND]
```
