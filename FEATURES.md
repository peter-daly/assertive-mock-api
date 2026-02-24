# Feature Backlog

This is the working feature list for the next iterations of Assertive Mock API.

## Now

### 1) Templated Responses Based on Request
Status: Implemented

Goal:
Return dynamic response content derived from request data (path params, query params, headers, and body).

MVP scope:
- Add template support to stub response `body` (string templates).
- Expose request context keys like `request.path`, `request.query.<key>`, `request.headers.<key>`, and `request.body`.
- Keep deterministic behavior: if a template key is missing, return a clear server error describing the missing key.

Acceptance criteria:
- A stub can respond with `"Hello {{ request.query.name }}"` and return `"Hello Peter"` when `?name=Peter`.
- Headers can be echoed in response body using template expressions.
- Existing static response stubs keep current behavior unchanged.

Open design questions:
- Template engine choice (simple safe interpolation vs Jinja2).
- Missing-key behavior (500 vs configurable fallback/defaults).

### 2) Mock SSE (Server-Sent Events) Responses
Status: Implemented

Goal:
Allow endpoints to simulate streaming event payloads for clients that consume SSE.

MVP scope:
- Add an SSE action type on stubs with an ordered list of events.
- Support event fields: `event`, `id`, `data`, optional `retry`.
- Return `Content-Type: text/event-stream` and stream events with configurable delay between events.

Acceptance criteria:
- A configured SSE stub streams multiple events in order.
- Clients can consume with `curl -N` or browser/EventSource and receive valid SSE frames.
- Stream can end cleanly after the final configured event.

Open design questions:
- Per-event delay vs global delay.
- Should SSE stubs allow infinite/repeating streams for soak tests.

### 3) Response Templating Helpers
Status: Proposed

Goal:
Provide built-in helper functions for dynamic mock values without custom code.

MVP scope:
- Add helpers for `uuid`, `now`, `random_int`, and `counter`.
- Make helpers available inside response templates.
- Keep helper evaluation deterministic per request where possible.

Acceptance criteria:
- A template can generate values like IDs and timestamps via helper calls.
- Counters can increment in a predictable way within a scope.
- Helper failures return clear template evaluation errors.

## Next

### 4) Response Delay and Fault Injection
Status: Partially Implemented

Goal:
Simulate realistic network conditions and service instability.

MVP scope:
- Per-stub fixed delay (ms). (Implemented)
- Optional random jitter range. (Implemented)
- Fault modes: connection close, timeout, and configurable 5xx bursts. (Not implemented)

### 5) Stateful Scenario Support
Status: Proposed

Goal:
Support multi-step flows where response changes after prior requests.

MVP scope:
- Scenario state key per scope.
- Stub precondition on state and action to transition state.
- Simple reset endpoint for scenario state.

### 6) Stub Import/Export
Status: Proposed

Goal:
Make test setup reproducible and portable.

MVP scope:
- Export current stubs and scopes as JSON.
- Import JSON bundle to recreate stubs/scopes.
- Validation errors that pinpoint invalid entries.

## Later

### 7) Rich Request Assertions
Status: Proposed

Goal:
Strengthen verification of request volume and sequence.

MVP scope:
- Assert request count (`exactly`, `at_least`, `at_most`).
- Assert ordered sequence across multiple request patterns.

### 8) Traffic Recording and Replay
Status: Proposed

Goal:
Capture real traffic and replay it as generated stubs.

MVP scope:
- Record inbound requests and chosen responses.
- Export to a replayable stub pack.

### 9) Chaos Profiles
Status: Proposed

Goal:
Apply reusable instability patterns across stubs without configuring faults one-by-one.

MVP scope:
- Define named profiles (e.g., `slow`, `flaky`, `error-burst`).
- Profile settings include delay/jitter/error-rate/timeout behavior.
- Allow applying a profile per stub and overriding select fields.

### 10) Admin UI
Status: Implemented

Goal:
Provide a browser-based control plane for faster local debugging and test setup.

MVP scope:
- List/create/edit/delete stubs and scopes.
- View recent request journal and matched stub details.
- Run common assertions from the UI (`did request happen`, count checks).

## Suggested Build Order

1. Templated Responses
2. Response Templating Helpers
3. Mock SSE
4. Delay/Fault Injection
5. Stateful Scenarios
6. Import/Export
7. Chaos Profiles
8. Admin UI
