import json
import warnings
from contextlib import contextmanager
from typing import Any

import httpx
from assertive import Criteria, as_json_matches, is_gte
from assertive.serialize import serialize
from pydantic import BaseModel, Field, model_validator


class StubRequestPayload(BaseModel):
    method: str | dict | None = None
    path: str | dict | None = None
    body: Any | None = None
    headers: dict | None = None
    host: str | dict | None = None
    query: dict | None = None


class StubResponsePayload(BaseModel):
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


class SseEventPayload(BaseModel):
    data: str
    event: str | None = None
    id: str | None = None
    retry: int | None = Field(default=None, ge=0)
    delay_ms: int | None = Field(default=None, ge=0)


class SseStreamPayload(BaseModel):
    events: list[SseEventPayload] = Field(min_length=1)
    default_delay_ms: int = Field(default=0, ge=0)


class StubProxyPayload(BaseModel):
    url: str
    headers: dict = Field(default_factory=dict)
    timeout: int = 5


class StubActionPayload(BaseModel):
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


class StubDelayPayload(BaseModel):
    base_ms: int = Field(default=0, ge=0)
    jitter_ms: int = Field(default=0, ge=0)


class StubConnectionDropPayload(BaseModel):
    probability: float = Field(ge=0, le=1)


class StubFaultsPayload(BaseModel):
    connection_drop: StubConnectionDropPayload | None = None


class StubChaosPayload(BaseModel):
    latency: StubDelayPayload = Field(default_factory=lambda: StubDelayPayload())
    faults: StubFaultsPayload = Field(default_factory=lambda: StubFaultsPayload())


class StubPayload(BaseModel):
    request: StubRequestPayload
    action: StubActionPayload
    max_calls: int | None = None
    chaos: StubChaosPayload | None = None


class ApiAssertionPayload(BaseModel):
    path: str | dict | None = None
    method: str | dict | None = None
    headers: dict | None = None
    body: Any | None = None
    host: str | dict | None = None
    query: dict | None = None
    times: int | dict | None


class _PreActionedStub:
    def __init__(self, mock_api: "MockApiClient", request: StubRequestPayload):
        self.mock_api = mock_api
        self.request = request
        self._chaos: StubChaosPayload | None = None

    def _ensure_chaos(self) -> StubChaosPayload:
        if self._chaos is None:
            self._chaos = StubChaosPayload()
        return self._chaos

    def with_latency(
        self,
        *,
        delay_ms: int,
        jitter_ms: int = 0,
    ) -> "_PreActionedStub":
        chaos = self._ensure_chaos()
        chaos.latency = StubDelayPayload(base_ms=delay_ms, jitter_ms=jitter_ms)
        return self

    def with_delay(
        self,
        *,
        delay_ms: int,
        jitter_ms: int = 0,
    ) -> "_PreActionedStub":
        warnings.warn(
            "with_delay(...) is deprecated; use with_latency(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.with_latency(delay_ms=delay_ms, jitter_ms=jitter_ms)

    def with_connection_drop(
        self,
        *,
        probability: float,
    ) -> "_PreActionedStub":
        chaos = self._ensure_chaos()
        chaos.faults = StubFaultsPayload(
            connection_drop=StubConnectionDropPayload(probability=probability)
        )
        return self

    def _create_stub(
        self, action: StubActionPayload, max_calls: int | None = None
    ) -> None:
        stub = StubPayload(
            request=self.request,
            action=action,
            max_calls=max_calls,
            chaos=self._chaos,
        )
        self.mock_api.create_stub(stub)

    def respond_with(
        self,
        *,
        status_code: int,
        headers: dict,
        body: Any,
        max_calls: int | None = None,
    ) -> None:
        """
        Responds with the given response.
        """
        response = StubResponsePayload(
            status_code=status_code,
            headers=headers,
            body=body,
        )

        action = StubActionPayload(response=response)
        self._create_stub(action=action, max_calls=max_calls)

    def respond_with_template(
        self,
        *,
        status_code: int,
        headers: dict = {},
        template_body: str,
        max_calls: int | None = None,
    ) -> None:
        """
        Responds with a rendered template body.
        """
        response = StubResponsePayload(
            status_code=status_code,
            headers=headers,
            template_body=template_body,
        )

        action = StubActionPayload(response=response)
        self._create_stub(action=action, max_calls=max_calls)

    def respond_with_json(
        self,
        *,
        status_code: int,
        body: dict,
        headers: dict = {},
        max_calls: int | None = None,
    ) -> None:
        return self.respond_with(
            status_code=status_code,
            headers={"Content-Type": "application/json", **headers},
            body=json.dumps(body),
            max_calls=max_calls,
        )

    def proxy_to(
        self,
        *,
        url: str,
        headers: dict = {},
        timeout: int = 5,
        max_calls: int | None = None,
    ) -> None:
        """
        Proxies the request to the given URL.
        """
        proxy = StubProxyPayload(url=url, headers=headers, timeout=timeout)
        action = StubActionPayload(proxy=proxy)
        self._create_stub(action=action, max_calls=max_calls)

    def respond_with_sse(
        self,
        *,
        events: list[dict],
        default_delay_ms: int = 0,
        max_calls: int | None = None,
    ) -> None:
        payload_events = [SseEventPayload.model_validate(event) for event in events]
        sse = SseStreamPayload(
            events=payload_events,
            default_delay_ms=default_delay_ms,
        )
        action = StubActionPayload(sse=sse)
        self._create_stub(action=action, max_calls=max_calls)


class MockApiClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8910",
        *,
        scope_name: str | None = None,
        scope_header_value: str = "1",
    ):
        self.base_url = base_url
        self._scope_name = scope_name
        self._scope_header_value = scope_header_value
        self._in_session = False
        self._session_stubs: list[str] = []

    def _scope_headers(self) -> dict[str, str]:
        if self._scope_name is None:
            return {}

        return {self._scope_name: self._scope_header_value}

    def create_scope(self, name: str) -> None:
        response = httpx.post(f"{self.base_url}/__mock__/scopes", json={"name": name})
        response.raise_for_status()

    def delete_scope(self, name: str) -> None:
        response = httpx.delete(f"{self.base_url}/__mock__/scopes/{name}")
        response.raise_for_status()
        self._scope_name = None

    def close_session(self) -> None:
        for stub_id in self._session_stubs:
            response = httpx.delete(f"{self.base_url}/__mock__/stubs/{stub_id}")
            response.raise_for_status()
        self._in_session = False
        self._session_stubs = []

    @contextmanager
    def new_session(self):
        if self._in_session:
            raise RuntimeError("Nested sessions are not supported")

        try:
            self._in_session = True
            yield self
        finally:
            self.close_session()

    @contextmanager
    def new_scope(self, scope_name: str):
        if self._in_session or self._scope_name is not None:
            raise RuntimeError("Nested scopes are not supported")

        self.create_scope(scope_name)

        scoped_client = MockApiClient(
            base_url=self.base_url,
            scope_name=scope_name,
            scope_header_value=self._scope_header_value,
        )

        try:
            yield scoped_client
        finally:
            self.delete_scope(scope_name)

    def when_requested_with(
        self,
        *,
        host: str | Criteria | None = None,
        headers: dict | Criteria | None = None,
        query: dict | Criteria | None = None,
        path: str | Criteria | None = None,
        method: str | Criteria | None = None,
        body: Any | None = None,
        json: Any | None = None,
    ) -> "_PreActionedStub":
        if json is not None and body is not None:
            raise ValueError("Cannot specify both body and json")

        if json is not None:
            body = as_json_matches(json)

        return _PreActionedStub(
            self,
            StubRequestPayload(
                headers=serialize(headers),
                path=serialize(path),
                method=serialize(method),
                body=serialize(body),
                host=serialize(host),
                query=serialize(query),
            ),
        )

    def create_stub(self, stub: StubPayload) -> None:
        """
        Stubs the request with the given stub.
        """

        # Convert the stub to a JSON object
        serialized_stub = stub.model_dump(exclude_unset=True, exclude_none=True)

        # Send the stub to the mock API server

        response = httpx.post(
            f"{self.base_url}/__mock__/stubs",
            json=serialized_stub,
            headers=self._scope_headers(),
        )

        response.raise_for_status()

        if self._in_session:
            stub_id = response.json()["stub_id"]
            self._session_stubs.append(stub_id)

    def confirm_request(
        self,
        *,
        host: str | Criteria | None = None,
        path: str | Criteria | None = None,
        method: str | Criteria | None = None,
        headers: dict | Criteria | None = None,
        body: Any | None = None,
        query: dict | Criteria | None = None,
        times: int | Criteria | None = is_gte(1),
    ) -> bool:
        """
        Confirms that the request was made.
        """

        assertion = ApiAssertionPayload(
            path=serialize(path),
            method=serialize(method),
            headers=serialize(headers),
            body=serialize(body),
            host=serialize(host),
            query=serialize(query),
            times=serialize(times),
        )

        response = httpx.post(
            f"{self.base_url}/__mock__/assert",
            json=assertion.model_dump(exclude_none=True, exclude_unset=True),
            headers=self._scope_headers(),
        )

        response.raise_for_status()
        json_response = response.json()

        result = json_response["result"]

        return result
