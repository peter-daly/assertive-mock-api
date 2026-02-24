import asyncio
import json
from typing import cast

import pytest
from fastapi.responses import JSONResponse, Response, StreamingResponse

from assertive_mock_api_server.app import (
    _build_drop_connection_response,
    _build_connection_drop_response,
    _build_sse_response,
    _build_standard_response,
    _template_render_error_response,
    _to_fastapi_response,
)
from assertive_mock_api_server.core import (
    MockApiDropConnectionResponse,
    MockApiResponse,
    MockApiSseResponse,
    SseEvent,
)
from assertive_mock_api_server.templating import TemplateRenderError


async def _read_stream(response: StreamingResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(_to_bytes(chunk))
    return b"".join(chunks)


def _to_bytes(chunk: str | bytes | memoryview) -> bytes:
    if isinstance(chunk, str):
        return chunk.encode("utf-8")
    if isinstance(chunk, memoryview):
        return chunk.tobytes()
    return chunk


def test_to_fastapi_response_dispatches_sse_and_non_sse():
    sse_response = MockApiSseResponse(events=[SseEvent(data="x")], default_delay_ms=0)
    sse_fastapi_response = _to_fastapi_response(sse_response)
    assert isinstance(sse_fastapi_response, StreamingResponse)

    normal_response = MockApiResponse(status_code=200, headers={}, body="ok")
    normal_fastapi_response = _to_fastapi_response(normal_response)
    assert isinstance(normal_fastapi_response, Response)
    assert not isinstance(normal_fastapi_response, StreamingResponse)


def test_to_fastapi_response_dispatches_drop_connection_wrapper():
    wrapped_response = MockApiDropConnectionResponse(
        status_code=200,
        headers={},
        body="ok",
    )
    fastapi_response = _to_fastapi_response(wrapped_response)
    assert isinstance(fastapi_response, StreamingResponse)


def test_build_standard_response_for_dict_uses_json_response():
    api_response = MockApiResponse(
        status_code=201,
        headers={"X-Test": "1"},
        body={"ok": True},
    )
    response = _build_standard_response(
        api_response,
    )
    assert isinstance(response, JSONResponse)
    assert response.status_code == 201
    assert response.headers["x-test"] == "1"
    response_body = _to_bytes(cast(str | bytes | memoryview, response.body))
    assert json.loads(response_body.decode("utf-8")) == {"ok": True}


def test_build_standard_response_for_str_bytes_and_none_preserves_behavior():
    str_response = _build_standard_response(
        MockApiResponse(status_code=200, headers={}, body="hello")
    )
    assert isinstance(str_response, Response)
    assert _to_bytes(cast(str | bytes | memoryview, str_response.body)) == b"hello"

    bytes_response = _build_standard_response(
        MockApiResponse(status_code=200, headers={}, body=b"binary")
    )
    assert isinstance(bytes_response, Response)
    assert _to_bytes(cast(str | bytes | memoryview, bytes_response.body)) == b"binary"
    assert bytes_response.headers["content-type"].startswith("application/octet-stream")

    none_response = _build_standard_response(
        MockApiResponse(status_code=204, headers={}, body=None)
    )
    assert isinstance(none_response, Response)
    assert none_response.status_code == 204
    assert _to_bytes(cast(str | bytes | memoryview, none_response.body)) == b""


def test_build_standard_response_keeps_status_and_headers():
    api_response = MockApiResponse(
        status_code=207,
        headers={"Content-Length": "100", "X-Test": "1"},
        body="abcdef",
    )

    response = _build_standard_response(api_response)
    assert isinstance(response, Response)
    assert response.status_code == 207
    assert response.headers["content-length"] == "100"
    assert response.headers["x-test"] == "1"
    assert _to_bytes(cast(str | bytes | memoryview, response.body)) == b"abcdef"


def test_build_drop_connection_response_for_non_sse_keeps_status_and_headers():
    api_response = MockApiDropConnectionResponse(
        status_code=207,
        headers={"Content-Length": "100", "X-Test": "1"},
        body="abcdef",
    )

    response = _build_drop_connection_response(api_response)
    assert isinstance(response, StreamingResponse)
    assert response.status_code == 207
    assert "content-length" not in response.headers
    assert response.headers["x-test"] == "1"

    async def verify_stream_behavior():
        iterator = response.body_iterator.__aiter__()
        first_chunk = await iterator.__anext__()
        assert _to_bytes(first_chunk) == b"abc"
        with pytest.raises(RuntimeError, match="Injected connection drop fault"):
            await iterator.__anext__()

    asyncio.run(verify_stream_behavior())


def test_build_connection_drop_response_infers_media_type_consistently():
    dict_response = _build_connection_drop_response(
        {"a": 1},
        status_code=200,
        headers={},
    )
    assert dict_response.headers["content-type"].startswith("application/json")

    bytes_response = _build_connection_drop_response(
        b"abc",
        status_code=200,
        headers={},
    )
    assert bytes_response.headers["content-type"].startswith("application/octet-stream")


def test_build_sse_response_preserves_headers_and_encoded_stream():
    api_response = MockApiSseResponse(
        events=[
            SseEvent(id="1", event="message", data="first"),
            SseEvent(id="2", event="message", data="second"),
        ],
        default_delay_ms=0,
    )

    response = _build_sse_response(api_response)
    assert isinstance(response, StreamingResponse)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"

    body = asyncio.run(_read_stream(response))
    assert body.decode("utf-8") == (
        "id: 1\nevent: message\ndata: first\n\nid: 2\nevent: message\ndata: second\n\n"
    )


def test_build_drop_connection_response_for_sse_streams_partial_then_aborts():
    api_response = MockApiDropConnectionResponse(
        status_code=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
        events=[
            SseEvent(id="1", event="message", data="first"),
            SseEvent(id="2", event="message", data="second"),
        ],
        default_delay_ms=0,
    )
    response = _build_drop_connection_response(api_response)
    assert isinstance(response, StreamingResponse)
    assert response.headers["content-type"].startswith("text/event-stream")

    async def verify_sse_drop_behavior():
        iterator = response.body_iterator.__aiter__()
        first_chunk = _to_bytes(await iterator.__anext__())
        assert first_chunk.startswith(b"id: 1\n")
        assert b"data: first\n\n" not in first_chunk
        with pytest.raises(RuntimeError, match="Injected connection drop fault"):
            await iterator.__anext__()

    asyncio.run(verify_sse_drop_behavior())


def test_template_render_error_response_preserves_shape():
    response = _template_render_error_response(TemplateRenderError("boom"))
    assert response.status_code == 500
    assert response.body == b'{"error":"TEMPLATE_RENDER_ERROR","detail":"boom"}'
