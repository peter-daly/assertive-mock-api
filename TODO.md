# Server Scope Feature TODO

## Current Status
Done

## Tasks
- [x] Create TODO.md and initialize plan tracking
- [x] Add scope domain support in `server/assertive_mock_api_server/core.py`
- [x] Add payload models in `server/assertive_mock_api_server/payloads.py`
- [x] Add scope endpoints and scope resolution in `server/assertive_mock_api_server/app.py`
- [x] Wire `ScopeRepository` in `server/assertive_mock_api_server/container.py`
- [x] Add/update server tests in `server/tests/`
- [x] Run server test suite and fix regressions introduced by scope changes
- [x] Finalize TODO.md status and completion notes

## Progress Log
- 2026-02-16: Created TODO.md and started implementation.
- 2026-02-16: Added scope domain model/repository, scoped filtering, and scope delete cascade handling in `core.py`.
- 2026-02-16: Added `CreateScopePayload` and scope visibility in request/stub view payloads.
- 2026-02-16: Added `/__mock__/scopes` endpoints and shared header-based scope resolution in `app.py`.
- 2026-02-16: Registered `ScopeRepository` singleton in dependency container.
- 2026-02-16: Added scope behavior coverage in `server/tests/test_scopes.py`.
- 2026-02-16: Fixed match ranking/regression behavior and validated with `12 passed` on server tests.
