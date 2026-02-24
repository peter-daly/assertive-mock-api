# Admin Pages

The server includes an in-app admin UI for managing stubs/scopes and inspecting recent traffic.

Base URL:

```text
/__admin__
```

## What It Includes

- Stub list with quick delete actions
- Scope list with create/delete actions
- Recent request log
- Stub detail pages
- Scope detail pages
- A guided page for creating stubs

The main dashboard uses HTMX polling to refresh panels.

## Page Routes

| Route | Method | Purpose |
| --- | --- | --- |
| `/__admin__` | `GET` | Main admin dashboard |
| `/__admin__/stubs/new` | `GET` | Create-stub UI |
| `/__admin__/stubs/{stub_id}` | `GET` | Stub detail page |
| `/__admin__/scopes/{name}` | `GET` | Scope detail page |

## Partial Routes (HTMX)

These return HTML fragments used by the dashboard.

| Route | Method | Purpose |
| --- | --- | --- |
| `/__admin__/partials/stubs` | `GET` | Refresh stubs panel |
| `/__admin__/partials/requests` | `GET` | Refresh requests panel |
| `/__admin__/partials/scopes` | `GET` | Refresh scopes panel |

## Action Routes (HTMX)

These are used by UI buttons/forms and return updated HTML fragments.

| Route | Method | Purpose |
| --- | --- | --- |
| `/__admin__/actions/stubs/{stub_id}` | `DELETE` | Delete a global stub |
| `/__admin__/actions/scopes/{name}` | `DELETE` | Delete a scope |

## Operational Notes

- The admin UI is intended for local/internal operational use.
- There is no built-in authentication layer on admin pages.
- In shared environments, place the app behind network restrictions and/or auth at the proxy/load-balancer layer.
- For automation and integration tests, prefer the JSON API under `/__mock__`.

See [API Usage](usage.md) for API-first examples.
