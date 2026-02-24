from typing import Any
from assertive import Criteria, ensure_criteria, has_key_values
from assertive.serialize import deserialize, serialize
from pydantic import BaseModel, Field, model_validator

from .core import (
    MockApiRequest,
    Stub,
    StubAction,
    StubChaos,
    StubDelay,
    StubRequest,
    StubProxy,
    StubResponse,
    SseEvent,
    SseStream,
    ApiAssertion,
)
from .path_matching import ensure_path_matcher, serialize_path_matcher


def ensure_str_criteria(data: str | dict | Criteria) -> Criteria:
    return deserialize(data)


def ensure_dict_criteria(data: dict | Criteria) -> Criteria:
    item = deserialize(data)

    if isinstance(item, dict):
        return has_key_values(item)

    return ensure_criteria(item)


class ApiAssertionPayload(BaseModel):
    """
    A request object for stubbing.
    """

    path: str | dict | None = None
    method: str | dict | None = None
    headers: dict | None = None
    body: str | dict | None = None
    host: str | dict | None = None
    query: dict | None = None
    times: str | dict | None = None

    def to_api_assertion(self) -> ApiAssertion:
        """
        Convert the request object to an ApiAssertion.
        """

        kwargs = {}

        if self.times is not None:
            kwargs["times"] = ensure_str_criteria(self.times)

        if self.path is not None:
            kwargs["path"] = ensure_str_criteria(self.path)

        if self.method is not None:
            kwargs["method"] = ensure_str_criteria(self.method)

        if self.body is not None:
            kwargs["body"] = ensure_str_criteria(self.body)

        if self.host is not None:
            kwargs["host"] = ensure_str_criteria(self.host)

        if self.headers is not None:
            kwargs["headers"] = ensure_dict_criteria(self.headers)

        if self.query is not None:
            kwargs["query"] = ensure_dict_criteria(self.query)

        return ApiAssertion(
            **kwargs,
        )


class CreateScopePayload(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")


class StubProxyPayload(BaseModel):
    """
    A proxy object for stubbing.
    """

    url: str
    headers: dict = Field(default_factory=dict)
    timeout: int = 5

    @classmethod
    def from_stub_proxy(cls, proxy: StubProxy) -> "StubProxyPayload":
        """
        Convert a stub proxy to a stub proxy payload.
        """
        return cls(
            url=proxy.url,
            headers=proxy.headers,
            timeout=proxy.timeout,
        )

    def to_stub_proxy(self) -> StubProxy:
        """
        Convert the proxy object to a stub proxy.
        """

        return StubProxy(
            url=self.url,
            headers=self.headers,
            timeout=self.timeout,
        )


class StubResponsePayload(BaseModel):
    """
    A response object for stubbing.
    """

    status_code: int
    headers: dict
    body: Any | None = None
    template_body: str | None = None

    @model_validator(mode="after")
    def _validate_body_xor_template_body(self):
        has_body = self.body is not None
        has_template_body = self.template_body is not None

        if has_body == has_template_body:
            raise ValueError("Exactly one of body or template_body must be provided.")
        return self

    @classmethod
    def from_stub_response(cls, response: StubResponse) -> "StubResponsePayload":
        """
        Convert a stub response to a stub response payload.
        """
        return cls(
            status_code=response.status_code,
            headers=response.headers,
            body=response.body,
            template_body=response.template_body,
        )

    def to_stub_response(self) -> StubResponse:
        """
        Convert the response object to a stub response.
        """

        return StubResponse(
            status_code=self.status_code,
            headers=self.headers,
            body=self.body,
            template_body=self.template_body,
        )


class SseEventPayload(BaseModel):
    data: str
    event: str | None = None
    id: str | None = None
    retry: int | None = Field(default=None, ge=0)
    delay_ms: int | None = Field(default=None, ge=0)

    @classmethod
    def from_sse_event(cls, event: SseEvent) -> "SseEventPayload":
        return cls(
            data=event.data,
            event=event.event,
            id=event.id,
            retry=event.retry,
            delay_ms=event.delay_ms,
        )

    def to_sse_event(self) -> SseEvent:
        return SseEvent(
            data=self.data,
            event=self.event,
            id=self.id,
            retry=self.retry,
            delay_ms=self.delay_ms,
        )


class SseStreamPayload(BaseModel):
    events: list[SseEventPayload] = Field(min_length=1)
    default_delay_ms: int = Field(default=0, ge=0)

    @classmethod
    def from_sse_stream(cls, stream: SseStream) -> "SseStreamPayload":
        return cls(
            events=[SseEventPayload.from_sse_event(event) for event in stream.events],
            default_delay_ms=stream.default_delay_ms,
        )

    def to_sse_stream(self) -> SseStream:
        return SseStream(
            events=[event.to_sse_event() for event in self.events],
            default_delay_ms=self.default_delay_ms,
        )


class StubRequestPayload(BaseModel):
    """
    A rough request object for stubbing.
    """

    method: str | dict | None = None
    path: str | dict | None = None
    body: Any | dict | None = None
    headers: dict | None = None
    host: str | dict | None = None
    query: dict | None = None

    @classmethod
    def from_stub_request(cls, request: StubRequest) -> "StubRequestPayload":
        """
        Convert a request object to a stub request payload.
        """
        return cls(
            method=serialize(request.method) if request.method else None,
            path=serialize_path_matcher(ensure_path_matcher(request.path))
            if request.path
            else None,
            body=serialize(request.body) if request.body else None,
            headers=serialize(request.headers) if request.headers else None,
            host=serialize(request.host) if request.host else None,
            query=serialize(request.query) if request.query else None,
        )

    def to_stub_request(self) -> StubRequest:
        """
        Convert the rough request object to a stub request.
        """
        kwargs = {}

        if self.path is not None:
            kwargs["path"] = ensure_path_matcher(self.path)

        if self.method is not None:
            kwargs["method"] = ensure_str_criteria(self.method)

        if self.body is not None:
            kwargs["body"] = ensure_str_criteria(self.body)

        if self.host is not None:
            kwargs["host"] = ensure_str_criteria(self.host)

        if self.headers is not None:
            kwargs["headers"] = ensure_dict_criteria(self.headers)

        if self.query is not None:
            kwargs["query"] = ensure_dict_criteria(self.query)

        return StubRequest(
            **kwargs,
        )


class StubActionPayload(BaseModel):
    """
    A stub action object for testing purposes.
    """

    response: StubResponsePayload | None = None
    proxy: StubProxyPayload | None = None
    sse: SseStreamPayload | None = None

    @model_validator(mode="after")
    def _validate_action_xor(self):
        configured_actions = [self.response, self.proxy, self.sse]
        configured_count = sum(1 for action in configured_actions if action is not None)
        if configured_count != 1:
            raise ValueError("Exactly one of response, proxy, or sse must be provided.")
        return self

    @classmethod
    def from_stub_action(cls, action: StubAction) -> "StubActionPayload":
        """
        Convert a stub action to a stub action payload.
        """
        return cls(
            response=StubResponsePayload.from_stub_response(action.response)
            if action.response
            else None,
            proxy=StubProxyPayload.from_stub_proxy(action.proxy)
            if action.proxy
            else None,
            sse=SseStreamPayload.from_sse_stream(action.sse) if action.sse else None,
        )

    def to_stub_action(self) -> StubAction:
        """
        Convert the action object to a stub action.
        """

        return StubAction(
            response=self.response.to_stub_response() if self.response else None,
            proxy=self.proxy.to_stub_proxy() if self.proxy else None,
            sse=self.sse.to_sse_stream() if self.sse else None,
        )


class StubChaosPayload(BaseModel):
    latency: "StubDelayPayload" = Field(default_factory=lambda: StubDelayPayload())

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_delay_fields(cls, data):
        if not isinstance(data, dict):
            return data
        if "latency" in data:
            return data
        if "delay" in data:
            data["latency"] = data.pop("delay")
            return data
        delay_ms = data.pop("delay_ms", None)
        jitter_ms = data.pop("jitter_ms", None)
        if delay_ms is not None or jitter_ms is not None:
            data["latency"] = {
                "base_ms": 0 if delay_ms is None else delay_ms,
                "jitter_ms": 0 if jitter_ms is None else jitter_ms,
            }
        return data

    @classmethod
    def from_stub_chaos(cls, chaos: StubChaos) -> "StubChaosPayload":
        return cls(latency=StubDelayPayload.from_stub_delay(chaos.latency))

    def to_stub_chaos(self) -> StubChaos:
        return StubChaos(latency=self.latency.to_stub_delay())


class StubDelayPayload(BaseModel):
    base_ms: int = Field(default=0, ge=0)
    jitter_ms: int = Field(default=0, ge=0)

    @classmethod
    def from_stub_delay(cls, delay: StubDelay) -> "StubDelayPayload":
        return cls(base_ms=delay.base_ms, jitter_ms=delay.jitter_ms)

    def to_stub_delay(self) -> StubDelay:
        return StubDelay(base_ms=self.base_ms, jitter_ms=self.jitter_ms)


StubChaosPayload.model_rebuild()


class StubPayload(BaseModel):
    """
    A request object for stubbing.
    """

    request: StubRequestPayload
    action: StubActionPayload
    max_calls: int | None = None
    chaos: StubChaosPayload | None = None

    def to_stub(self, scope: str | None = None) -> Stub:
        """
        Convert the request object to a stub.
        """
        stub = Stub(
            request=self.request.to_stub_request(),
            action=self.action.to_stub_action(),
            scope=scope,
            chaos=self.chaos.to_stub_chaos() if self.chaos else None,
        )
        if self.max_calls is not None:
            stub.max_calls = self.max_calls
        return stub


class StubViewPayload(BaseModel):
    """
    A response object for stubbing.
    """

    stub_id: str
    request: StubRequestPayload
    action: StubActionPayload
    scope: str | None = None
    chaos: StubChaosPayload | None = None


class StubListViewPayload(BaseModel):
    """
    A response object for stubbing.
    """

    stubs: list[StubViewPayload] = Field(default_factory=list)

    @classmethod
    def from_stubs(cls, stubs: list[Stub]) -> "StubListViewPayload":
        """
        Convert a list of stubs to a list of stub views.
        """
        return cls(
            stubs=[
                StubViewPayload(
                    stub_id=stub.stub_id,
                    request=StubRequestPayload.from_stub_request(stub.request),
                    action=StubActionPayload.from_stub_action(stub.action),
                    scope=stub.scope,
                    chaos=StubChaosPayload.from_stub_chaos(stub.chaos)
                    if stub.chaos
                    else None,
                )
                for stub in stubs
            ]
        )


class MockApiRequestViewPayload(BaseModel):
    """
    A view payload for a mock API request.
    """

    method: str
    path: str
    query: dict
    headers: dict
    body: str | bytes
    host: str
    scope: str | None = None
    matched_stub_id: str | None = None

    @classmethod
    def from_mock_api_request(
        cls, request: MockApiRequest
    ) -> "MockApiRequestViewPayload":
        """
        Convert a mock API request to a view payload.
        """
        return cls(
            method=request.method,
            path=request.path,
            query=request.query,
            headers=request.headers,
            body=request.body,
            host=request.host,
            scope=request.scope,
            matched_stub_id=request.matched_stub_id,
        )


class MockApiRequestListViewPayload(BaseModel):
    """
    A view payload for a list of mock API requests.
    """

    requests: list[MockApiRequestViewPayload] = Field(default_factory=list)

    @classmethod
    def from_mock_api_requests(
        cls, requests: list[MockApiRequest]
    ) -> "MockApiRequestListViewPayload":
        """
        Convert a list of mock API requests to a view payload.
        """
        return cls(
            requests=[
                MockApiRequestViewPayload.from_mock_api_request(request)
                for request in requests
            ]
        )
