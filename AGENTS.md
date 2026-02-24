# AGENTS.md

## Purpose
This repo (`assertive-mock-api-server`) matches requests using the `assertive` criteria system.

When making design or code decisions, treat criteria behavior and wire serialization as the source of truth, not plain string/dict equality.

## Dependency Source Of Truth (Venv)
`assertive` is a dependency. On any machine, inspect the installed package in the active virtual environment when behavior is unclear.

Primary modules to trust first:
- `assertive.core`
  - Defines `Criteria`, `ensure_criteria`, and logical composition semantics.
- `assertive.serialize`
  - Defines wire operator mapping plus `serialize(...)` / `deserialize(...)` behavior.

Useful checks:
- Locate installed module:
  - `python -c "import assertive; print(assertive.__file__)"`
- Confirm installed version:
  - `python -c "import importlib.metadata as m; print(m.version('assertive'))"`
- Inspect primary modules:
  - `python -c "import inspect, assertive.core as c, assertive.serialize as s; print(inspect.getsourcefile(c)); print(inspect.getsourcefile(s))"`
- Validate serialization operator map at runtime:
  - `python -c "from assertive.serialize import SERIALIZABLE_CRITERIA; print(list(SERIALIZABLE_CRITERIA.keys()))"`

Decision rule:
- Prefer behavior from the installed dependency over assumptions from memory.

## System Components (What They Do)
- Criteria engine:
  - Provides `Criteria` objects used for all matcher evaluation.
  - Wraps literal values with equality criteria via `ensure_criteria(...)`.
  - Supports composition (`and/or/xor/not`) to build complex matchers.
- Serialization layer:
  - Converts criteria objects to JSON-safe operator shapes (for transport).
  - Rebuilds criteria objects from operator-shaped JSON on the receiving side.
- Payload normalization layer (server input side):
  - Converts incoming stub/assert payloads into executable criteria.
  - Applies dictionary matcher defaults for headers/query (`has_key_values` subset matching).
- Matching engine:
  - Evaluates request fields against criteria-based stub predicates.
  - Uses match strength (number of matched configured fields) to pick the best stub.
- Client API:
  - Accepts either literals or criteria instances.
  - Serializes criteria automatically before calling control endpoints.

## Criteria Mental Model (Assertive)
- Any matcher is a `Criteria` object.
- Canonical source: `assertive.core`.
- `ensure_criteria(value)` wraps non-criteria values as `is_eq(value)`.
- Logical composition:
  - `a & b` -> `AndCriteria`
  - `a | b` -> `OrCriteria`
  - `a ^ b` -> `XorCriteria`
  - `~a` -> `InvertedCriteria`
- Matching is driven by comparison with criteria (`subject == criteria` / `subject != criteria`).
  - In this codebase, stub matching and assertions rely on this behavior heavily.

## Where This Repo Converts Payloads Into Criteria
- `ensure_str_criteria(data)`:
  - `deserialize(data)` first
  - then `ensure_criteria(...)`
- `ensure_dict_criteria(data)`:
  - `deserialize(data)` first
  - if result is still a plain dict -> wraps with `has_key_values(...)`
  - else returns criteria directly

Used by:
- `StubRequestPayload.to_stub_request()`
- `ApiAssertionPayload.to_api_assertion()`

Do not bypass these conversion points when adding fields/endpoints.

## Matching Semantics In This Repo
- `Stub.matches_request(...)` checks configured fields (`method/path/headers/body/host/query`) using criteria comparisons.
- `ApiAssertion.matches_requests(...)` applies same criteria logic across logged requests.
- Stub strength = number of configured matcher fields that pass; stronger match wins.

Important behavior:
- `headers` and `query` sent as plain dicts become `has_key_values(...)` (subset match, not exact dict equality).
- A stub with no predicates is a catch-all.

## Wire Format: Serialization/Deserialization Contract
Criteria cross client/server boundaries via `assertive.serialize.serialize` and `deserialize`.
Canonical source: `assertive.serialize`.

Supported serializable keys:
- `$gt`, `$gte`, `$lt`, `$lte`, `$between`, `$eq`, `$neq`
- `$and`, `$or`, `$xor`, `$not`
- `$json`, `$contains`, `$contains_exactly`, `$regex`, `$length`
- `$key_values`, `$exact_key_values`
- `$even`, `$odd`, `$ignore_case`

Rules:
- `serialize(...)` recurses into lists/dicts.
- Criteria are serialized as `{ "<op>": { ...fields... } }`.
- `deserialize(...)` rebuilds criteria recursively.
- Deserialization is kwargs-driven:
  - operator payload value is treated as kwargs and passed into `from_serialized(kwargs)`
  - default behavior then calls criteria constructors with keyword args
  - payload keys must match expected parameter names/shape for that criteria
- If a dict has no recognized criteria key, it stays a plain dict.

Caution:
- Do not mix a criteria operator key with sibling keys in the same dict payload (e.g. `{"$gt": ..., "x": ...}`); deserialization treats it as a criteria object shape.

## Client Behavior You Should Assume
- `when_requested_with(...)` serializes matcher inputs before POSTing stubs.
- `confirm_request(...)` serializes assertion inputs (including `times`).
- `json=...` helper wraps body as `as_json_matches(...)` before serialization.

Practical implication:
- For JSON-body structural matching, prefer `json=...` (or explicit `$json` criteria payload), not raw dict body equality.

## Limits / Pitfalls
- Only criteria classes in `SERIALIZABLE_CRITERIA` are wire-safe.
  - If a criteria type is not in that map, it will not serialize into JSON operator form.
- Custom/new criteria are not automatically transportable between client and server.
- If you add a new wire-safe criteria type, update:
  - the serialization operator map (`SERIALIZABLE_CRITERIA`)
  - serialization/deserialization test coverage
  - API docs/examples that list allowed operator keys

## Agent Decision Rules For This Repo
1. Prefer using `MockApiClient` with criteria objects over crafting raw serialized dicts manually.
2. If raw HTTP payloads are needed, use the exact serialized operator shapes above.
3. When debugging mismatches, inspect how payload fields were converted (`ensure_str_criteria` vs `ensure_dict_criteria`) before changing matching logic.
4. Do not "simplify" matching to plain equality without verifying criteria behavior impact.
5. Keep criteria compatibility between client and server versions aligned; serialization map drift causes subtle failures.
