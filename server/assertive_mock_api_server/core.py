"""
This is a test bed for the assertive-mock-api.
"""

import asyncio
import random
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx
from assertive import Criteria, is_gte
from pydantic import model_validator

from .path_matching import PathMatcher, ensure_path_matcher
from .templating import render_template

PRACTICALLY_INFINITE = 2**31
SCOPE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class ScopeAlreadyExistsError(ValueError):
    pass


class ScopeNotFoundError(ValueError):
    pass


class InvalidScopeNameError(ValueError):
    pass


def normalize_scope_name(name: str) -> str:
    if not SCOPE_NAME_PATTERN.fullmatch(name):
        raise InvalidScopeNameError(
            "Scope name must be token-safe and contain only letters, digits, '-' or '_'"
        )
    return name.lower()


@dataclass(kw_only=True)
class MockApiRequest:
    path: str
    method: str
    headers: dict
    body: Any
    host: str
    query: dict
    scope: str | None = None
    matched_stub_id: str | None = None
    path_params: dict[str, str] = field(default_factory=dict)


@dataclass(kw_only=True)
class ApiAssertion:
    path: Criteria | None = None
    method: Criteria | None = None
    headers: Criteria | None = None
    body: Criteria | None = None
    host: Criteria | None = None
    query: Criteria | None = None
    times: Criteria = field(default_factory=lambda: is_gte(1))

    class Config:
        arbitrary_types_allowed = True

    def _matches_request(self, request: MockApiRequest) -> bool:
        """
        Check if the request matches the stub.
        """

        fields_to_check = ["method", "path", "headers", "body", "host", "query"]
        for check in fields_to_check:
            if getattr(self, check) is not None:
                if getattr(request, check) != getattr(self, check):
                    return False
        return True

    def matches_requests(self, requests: list[MockApiRequest]) -> bool:
        matches = [request for request in requests if self._matches_request(request)]

        return len(matches) == self.times


@dataclass(kw_only=True)
class StubRequest:
    """
    A stub request object for testing purposes.
    """

    method: Criteria | None = None
    path: PathMatcher | Criteria | str | dict | None = None
    headers: Criteria | None = None
    body: Criteria | None = None
    host: Criteria | None = None
    query: Criteria | None = None

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path = ensure_path_matcher(self.path)

    class Config:
        arbitrary_types_allowed = True


@dataclass(kw_only=True)
class StubResponse:
    """
    A stub response object for testing purposes.
    """

    status_code: int
    headers: dict
    body: Any | None = None
    template_body: str | None = None

    def __post_init__(self) -> None:
        has_body = self.body is not None
        has_template_body = self.template_body is not None

        if has_body == has_template_body:
            raise ValueError("Exactly one of body or template_body must be provided.")

    class Config:
        arbitrary_types_allowed = True


@dataclass(kw_only=True)
class StubProxy:
    """
    A stub proxy object for testing purposes.
    """

    url: str
    headers: dict = field(default_factory=dict)
    timeout: int = 5

    class Config:
        arbitrary_types_allowed = True


@dataclass(kw_only=True)
class SseEvent:
    data: str
    event: str | None = None
    id: str | None = None
    retry: int | None = None
    delay_ms: int | None = None

    def __post_init__(self) -> None:
        if self.retry is not None and self.retry < 0:
            raise ValueError("retry must be >= 0")
        if self.delay_ms is not None and self.delay_ms < 0:
            raise ValueError("delay_ms must be >= 0")


@dataclass(kw_only=True)
class SseStream:
    events: list[SseEvent]
    default_delay_ms: int = 0

    def __post_init__(self) -> None:
        if not self.events:
            raise ValueError("events must not be empty")
        if self.default_delay_ms < 0:
            raise ValueError("default_delay_ms must be >= 0")


@dataclass(kw_only=True)
class StubAction:
    """
    A stub action object for testing purposes.
    """

    response: StubResponse | None = None
    proxy: StubProxy | None = None
    sse: SseStream | None = None

    def __post_init__(self) -> None:
        configured_actions = [self.response, self.proxy, self.sse]
        configured_count = sum(1 for action in configured_actions if action is not None)
        if configured_count != 1:
            raise ValueError("Exactly one of response, proxy, or sse must be provided.")

    @model_validator(mode="after")
    def _validate_response_and_proxy(self):
        """
        Validates the action object.
        """
        configured_actions = [self.response, self.proxy, self.sse]
        configured_count = sum(1 for action in configured_actions if action is not None)
        if configured_count != 1:
            raise ValueError("Exactly one of response, proxy, or sse must be provided.")
        return self

    class Config:
        arbitrary_types_allowed = True


@dataclass(kw_only=True)
class StubDelay:
    base_ms: int = 0
    jitter_ms: int = 0

    def __post_init__(self) -> None:
        if self.base_ms < 0:
            raise ValueError("base_ms must be >= 0")
        if self.jitter_ms < 0:
            raise ValueError("jitter_ms must be >= 0")


@dataclass(kw_only=True)
class StubConnectionDrop:
    probability: float = 1.0

    def __post_init__(self) -> None:
        if self.probability < 0 or self.probability > 1:
            raise ValueError("probability must be between 0 and 1")


@dataclass(kw_only=True)
class StubFaults:
    connection_drop: StubConnectionDrop | None = None


@dataclass(kw_only=True)
class StubChaos:
    latency: StubDelay = field(default_factory=StubDelay)
    faults: StubFaults = field(default_factory=StubFaults)


@dataclass(kw_only=True)
class StubMatch:
    strength: int
    stub: "Stub"
    path_params: dict[str, str] = field(default_factory=dict)
    path_specificity: int = 0


@dataclass(kw_only=True)
class Stub:
    """
    A stub object for testing purposes.
    """

    request: StubRequest
    action: StubAction

    stub_id: str = field(default_factory=lambda: str(uuid4()))
    call_count: int = 0
    max_calls: int = PRACTICALLY_INFINITE
    scope: str | None = None
    chaos: StubChaos | None = None

    def matches_request(self, request: MockApiRequest) -> StubMatch:
        """
        Check if the request matches the stub.
        """
        if self.call_count >= self.max_calls:
            return StubMatch(strength=0, stub=self)

        strength = 0
        path_params: dict[str, str] = {}
        path_specificity = 0

        if self.request.path is not None:
            path_matcher = ensure_path_matcher(self.request.path)
            path_match = path_matcher.match(request.path)
            if not path_match.matched:
                return StubMatch(strength=0, stub=self)
            strength += 1
            path_params = path_match.params
            path_specificity = path_match.specificity

        fields_to_check = ["method", "headers", "body", "host", "query"]
        for check_field in fields_to_check:
            if getattr(self.request, check_field) is not None:
                if getattr(request, check_field) != getattr(self.request, check_field):
                    return StubMatch(strength=0, stub=self)
                strength += 1

        # A stub with no match predicates is a valid catch-all match.
        if strength == 0:
            strength = 1

        self.call_count += 1
        return StubMatch(
            strength=strength,
            stub=self,
            path_params=path_params,
            path_specificity=path_specificity,
        )


class ScopeRepository:
    def __init__(self):
        self.scopes: dict[str, str] = {}

    def create(self, name: str) -> str:
        normalized = normalize_scope_name(name)
        if normalized in self.scopes:
            raise ScopeAlreadyExistsError(f"Scope '{name}' already exists")
        self.scopes[normalized] = normalized
        return normalized

    def delete(self, name: str) -> str:
        normalized = normalize_scope_name(name)
        if normalized not in self.scopes:
            raise ScopeNotFoundError(f"Scope '{name}' was not found")
        del self.scopes[normalized]
        return normalized

    def list_scopes(self) -> list[str]:
        return list(self.scopes.values())

    def resolve_from_headers(self, headers: dict) -> list[str]:
        header_keys = {str(key).lower() for key in headers.keys()}
        return [scope for scope in self.scopes if scope in header_keys]


class RequestLog:
    def __init__(self):
        self.global_requests: list[MockApiRequest] = []
        self.scoped_requests: dict[str, list[MockApiRequest]] = {}

    def add(self, request: MockApiRequest) -> None:
        """
        Adds a request to the log.
        """
        if request.scope is None:
            self.global_requests.append(request)
            return

        if request.scope not in self.scoped_requests:
            self.scoped_requests[request.scope] = []
        self.scoped_requests[request.scope].append(request)

    def list_for_scope(self, scope: str | None) -> list[MockApiRequest]:
        if scope is None:
            return list(self.global_requests)

        scoped_requests = self.scoped_requests.get(scope, [])
        global_requests = self.global_requests
        return scoped_requests + global_requests

    def delete_scope(self, scope: str) -> None:
        self.scoped_requests.pop(scope, None)


class StubRepository:
    def __init__(self):
        self.global_stubs: list[Stub] = []
        self.scoped_stubs: dict[str, list[Stub]] = {}

    def add(self, stub: Stub) -> None:
        """
        Adds a stub to the repository.
        """
        if stub.scope is None:
            self.global_stubs.append(stub)
            return

        if stub.scope not in self.scoped_stubs:
            self.scoped_stubs[stub.scope] = []
        self.scoped_stubs[stub.scope].append(stub)

    def list_for_scope(self, scope: str | None) -> list[Stub]:
        if scope is None:
            return list(self.global_stubs)

        scoped_stubs = self.scoped_stubs.get(scope, [])
        global_stubs = self.global_stubs
        return scoped_stubs + global_stubs

    def delete_scope(self, scope: str) -> None:
        self.scoped_stubs.pop(scope, None)

    def delete_by_id(self, stub_id: str, scope: str | None = None) -> bool:
        if scope is None:
            for index, stub in enumerate(self.global_stubs):
                if stub.stub_id == stub_id:
                    del self.global_stubs[index]
                    return True
            return False

        scoped_items = self.scoped_stubs.get(scope, [])
        for index, stub in enumerate(scoped_items):
            if stub.stub_id == stub_id:
                del scoped_items[index]
                return True

        for index, stub in enumerate(self.global_stubs):
            if stub.stub_id == stub_id:
                del self.global_stubs[index]
                return True

        return False

    def find_best_match(self, request: MockApiRequest) -> Stub | None:
        best_match = self.find_best_match_result(request)
        return best_match.stub if best_match is not None else None

    def find_best_match_result(self, request: MockApiRequest) -> StubMatch | None:
        """
        Finds the best match for the given request.
        """
        best_match: StubMatch | None = None
        best_rank = (0, -1, -1)

        for stub in self.list_for_scope(request.scope):
            match = stub.matches_request(request)
            if match.strength <= 0:
                continue
            scope_specificity = (
                1 if request.scope is not None and stub.scope == request.scope else 0
            )
            rank = (match.strength, scope_specificity, match.path_specificity)
            if rank > best_rank:
                best_rank = rank
                best_match = match

        return best_match

    class Config:
        arbitrary_types_allowed = True


@dataclass(kw_only=True)
class MockApiResponse:
    status_code: int
    headers: dict
    body: Any

    @staticmethod
    def no_stub_found() -> "MockApiResponse":
        """
        Returns a response indicating that no stub was found.
        """
        return MockApiResponse(
            status_code=404,
            headers={},
            body="NO_STUB_MATCH_FOUND",
        )


@dataclass(kw_only=True)
class MockApiSseResponse:
    events: list[SseEvent]
    default_delay_ms: int = 0


@dataclass(kw_only=True)
class MockApiDropConnectionResponse:
    status_code: int
    headers: dict
    body: Any | None = None
    events: list[SseEvent] | None = None
    default_delay_ms: int = 0

    def __post_init__(self) -> None:
        if self.body is not None and self.events is not None:
            raise ValueError("Only one of body or events can be set on drop response")
        if self.events is not None and not self.events:
            raise ValueError("events must not be empty when provided")


def resolve_stub_delay_ms(stub: Stub) -> int:
    if stub.chaos is None:
        return 0
    if stub.chaos.latency.jitter_ms == 0:
        return stub.chaos.latency.base_ms
    return random.randint(
        stub.chaos.latency.base_ms,
        stub.chaos.latency.base_ms + stub.chaos.latency.jitter_ms,
    )


def should_drop_connection(stub: Stub) -> bool:
    if stub.chaos is None:
        return False
    if stub.chaos.faults.connection_drop is None:
        return False
    return random.random() < stub.chaos.faults.connection_drop.probability


def resolve_sse_delay_ms(event: SseEvent, default_delay_ms: int) -> int:
    if event.delay_ms is not None:
        return event.delay_ms
    return default_delay_ms


def encode_sse_event(event: SseEvent) -> str:
    lines: list[str] = []

    if event.id is not None:
        lines.append(f"id: {event.id}")
    if event.event is not None:
        lines.append(f"event: {event.event}")
    if event.retry is not None:
        lines.append(f"retry: {event.retry}")

    data_lines = event.data.splitlines() or [""]
    lines.extend(f"data: {line}" for line in data_lines)
    lines.append("")
    return "\n".join(lines) + "\n"


def render_sse_event_templates(event: SseEvent, request: MockApiRequest) -> SseEvent:
    rendered_data = render_template(event.data, request)
    rendered_event = (
        render_template(event.event, request) if event.event is not None else None
    )
    rendered_id = render_template(event.id, request) if event.id is not None else None

    return SseEvent(
        data=rendered_data,
        event=rendered_event,
        id=rendered_id,
        retry=event.retry,
        delay_ms=event.delay_ms,
    )


class ResponseGenerator:
    """
    A generator for creating responses.
    """

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def generate(
        self, stub: Stub, request: MockApiRequest
    ) -> MockApiResponse | MockApiSseResponse:
        """
        Generates a response.
        """
        if stub_response := stub.action.response:
            if stub_response.template_body is not None:
                response_body = render_template(stub_response.template_body, request)
            else:
                response_body = stub_response.body

            return MockApiResponse(
                status_code=stub_response.status_code,
                headers=stub_response.headers,
                body=response_body,
            )

        if stub_proxy := stub.action.proxy:
            headers = request.headers.copy()
            headers.update(stub_proxy.headers)

            proxied_response = await self.client.request(
                method=request.method,
                url=stub_proxy.url,
                headers=headers,
                data=request.body,
                params=request.query,
                timeout=stub_proxy.timeout,
            )

            return MockApiResponse(
                status_code=proxied_response.status_code,
                headers=dict(proxied_response.headers),
                body=proxied_response.content,
            )

        if stub_sse := stub.action.sse:
            rendered_events = [
                render_sse_event_templates(event, request) for event in stub_sse.events
            ]
            return MockApiSseResponse(
                events=rendered_events,
                default_delay_ms=stub_sse.default_delay_ms,
            )

        raise ValueError("No response, proxy, or sse found in the stub.")


@dataclass(kw_only=True)
class ConfirmResult:
    """
    A result object for the confirm method.
    """

    success: bool


class MockApiServer:
    """
    A mock API server for testing purposes.
    """

    def __init__(
        self,
        stub_repository: StubRepository,
        request_log: RequestLog,
        response_generator: ResponseGenerator,
        scope_repository: ScopeRepository,
    ):
        self.stub_repository = stub_repository
        self.request_log = request_log
        self.response_generator = response_generator
        self.scope_repository = scope_repository

    async def handle_request(
        self, request: MockApiRequest
    ) -> MockApiResponse | MockApiSseResponse | MockApiDropConnectionResponse:
        """
        Handles the given request and returns a response.
        """
        best_match = self.stub_repository.find_best_match_result(request)
        request.matched_stub_id = (
            best_match.stub.stub_id if best_match is not None else None
        )
        request.path_params = best_match.path_params if best_match is not None else {}
        self.request_log.add(request)

        if best_match is None:
            return MockApiResponse.no_stub_found()

        delay_ms = resolve_stub_delay_ms(best_match.stub)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)

        response = await self.response_generator.generate(best_match.stub, request)
        if should_drop_connection(best_match.stub):
            if isinstance(response, MockApiSseResponse):
                return MockApiDropConnectionResponse(
                    status_code=200,
                    headers={
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    },
                    events=response.events,
                    default_delay_ms=response.default_delay_ms,
                )
            return MockApiDropConnectionResponse(
                status_code=response.status_code,
                headers=response.headers,
                body=response.body,
            )
        return response

    async def add_stub(self, stub: Stub) -> None:
        """
        Stubs a request with the given parameters.
        """
        self.stub_repository.add(stub)

    async def confirm_assertion(
        self, assertion: ApiAssertion, scope: str | None = None
    ) -> ConfirmResult:
        requests = self.request_log.list_for_scope(scope)
        result = assertion.matches_requests(requests)
        return ConfirmResult(success=result)

    async def list_stubs(self, scope: str | None = None) -> list[Stub]:
        """
        Lists all stubs in the repository.
        """
        return self.stub_repository.list_for_scope(scope)

    async def delete_stub(self, stub_id: str, scope: str | None = None) -> bool:
        return self.stub_repository.delete_by_id(stub_id, scope)

    async def list_requests(self, scope: str | None = None) -> list[MockApiRequest]:
        """
        Lists all requests in the log.
        """
        return self.request_log.list_for_scope(scope)

    async def create_scope(self, name: str) -> str:
        return self.scope_repository.create(name)

    async def delete_scope(self, name: str) -> str:
        scope = self.scope_repository.delete(name)
        self.stub_repository.delete_scope(scope)
        self.request_log.delete_scope(scope)
        return scope

    async def list_scopes(self) -> list[str]:
        return self.scope_repository.list_scopes()
