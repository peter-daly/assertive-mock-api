"""
This is a test bed for the assertive-mock-api.
"""

from typing import Any
from assertive import Criteria, is_gte
from pydantic import model_validator
import httpx


from dataclasses import dataclass, field

PRACTICALLY_INFINITE = 2**31


@dataclass(kw_only=True)
class MockApiRequest:
    path: str
    method: str
    headers: dict
    body: Any
    host: str
    query: dict


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
    path: Criteria | None = None
    headers: Criteria | None = None
    body: Criteria | None = None
    host: Criteria | None = None
    query: Criteria | None = None

    class Config:
        arbitrary_types_allowed = True


@dataclass(kw_only=True)
class StubResponse:
    """
    A stub response object for testing purposes.
    """

    status_code: int
    headers: dict
    body: Any

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
class StubAction:
    """
    A stub action object for testing purposes.
    """

    response: StubResponse | None = None
    proxy: StubProxy | None = None

    @model_validator(mode="after")
    def _validate_response_and_proxy(self):
        """
        Validates the action object.
        """
        if self.response is None and self.proxy is None:
            raise ValueError("Either response or proxy must be provided.")
        if self.response is not None and self.proxy is not None:
            raise ValueError("Only one of response or proxy can be provided.")
        return self

    class Config:
        arbitrary_types_allowed = True


@dataclass(kw_only=True)
class StubMatch:
    strength: int
    stub: "Stub"


@dataclass(kw_only=True)
class Stub:
    """
    A stub object for testing purposes.
    """

    request: StubRequest
    action: StubAction

    call_count: int = 0
    max_calls: int = PRACTICALLY_INFINITE

    def matches_request(self, request: MockApiRequest) -> StubMatch:
        """
        Check if the request matches the stub.
        """
        if self.call_count >= self.max_calls:
            return StubMatch(strength=0, stub=self)

        strength = 0
        fields_to_check = ["method", "path", "headers", "body", "host", "query"]

        for check_field in fields_to_check:
            if getattr(self.request, check_field) is not None:
                if getattr(request, check_field) != getattr(self.request, check_field):
                    return StubMatch(strength=0, stub=self)
                strength += 1

        self.call_count += 1
        return StubMatch(strength=strength, stub=self)


class RequestLog:
    def __init__(self):
        self.requests: list[MockApiRequest] = []

    def add(self, request: MockApiRequest) -> None:
        """
        Adds a request to the log.
        """
        self.requests.append(request)

    def get_requests(self) -> list[MockApiRequest]:
        """
        Finds all requests that match the given assertion.
        """
        return self.requests


class StubRepository:
    def __init__(self):
        self.stubs: list[Stub] = []

    def add(self, stub: Stub) -> None:
        """
        Adds a stub to the repository.
        """
        self.stubs.append(stub)

    def find_best_match(self, request: MockApiRequest) -> Stub | None:
        """
        Finds the best match for the given request.
        """
        best_match = None
        best_strength = 0

        for stub in self.stubs:
            match = stub.matches_request(request)
            if match.strength > best_strength:
                best_strength = match.strength
                best_match = match.stub

        return best_match

    def list(self) -> list[Stub]:
        """
        Lists all stubs in the repository.
        """
        return self.stubs

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


class ResponseGenerator:
    """
    A generator for creating responses.
    """

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def generate(self, stub: Stub, request: MockApiRequest) -> MockApiResponse:
        """
        Generates a response.
        """
        if stub_response := stub.action.response:
            return MockApiResponse(
                status_code=stub_response.status_code,
                headers=stub_response.headers,
                body=stub_response.body,
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

        raise ValueError("No response or proxy found in the stub.")


@dataclass(kw_only=True)
class ConfirmResult:
    """
    A result object for the conform method.
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
    ):
        self.stub_repository = stub_repository
        self.request_log = request_log
        self.response_generator = response_generator

    async def handle_request(self, request: MockApiRequest) -> MockApiResponse:
        """
        Handles the given request and returns a response.
        """
        self.request_log.add(request)

        best_match = self.stub_repository.find_best_match(request)
        if best_match is None:
            return MockApiResponse.no_stub_found()
        response = await self.response_generator.generate(best_match, request)
        return response

    async def add_stub(self, stub: Stub) -> None:
        """
        Stubs a request with the given parameters.
        """
        self.stub_repository.add(stub)

    async def confirm_assertion(self, assertion: ApiAssertion) -> ConfirmResult:
        requests = self.request_log.get_requests()
        result = assertion.matches_requests(requests)
        return ConfirmResult(success=result)

    async def list_stubs(self) -> list[Stub]:
        """
        Lists all stubs in the repository.
        """
        stubs = self.stub_repository.list()
        return stubs

    async def list_requests(self) -> list[MockApiRequest]:
        """
        Lists all requests in the log.
        """
        return self.request_log.get_requests()
