import asyncio
import socket
import threading
import time
from contextlib import contextmanager
from typing import Iterator

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Response

from assertive_mock_api_server.app import app as mock_app


def _find_free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def _run_uvicorn(app) -> Iterator[str]:
    port = _find_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(
        target=lambda: asyncio.run(server.serve()),
        daemon=True,
    )
    thread.start()

    deadline = time.time() + 5
    while not server.started and time.time() < deadline:
        time.sleep(0.01)

    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("uvicorn test server did not start")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _create_stub(base_url: str, payload: dict) -> None:
    response = httpx.post(f"{base_url}/__mock__/stubs", json=payload, timeout=5.0)
    assert response.status_code == 200, response.text


def _connection_drop_chaos(probability: float) -> dict:
    return {"faults": {"connection_drop": {"probability": probability}}}


def test_response_connection_drop_probability_one_interrupts_client():
    with _run_uvicorn(mock_app) as base_url:
        _create_stub(
            base_url,
            {
                "request": {"path": "/drop-response", "method": "GET"},
                "action": {
                    "response": {
                        "status_code": 200,
                        "headers": {"Content-Type": "text/plain"},
                        "body": "response-body-that-will-be-cut",
                    }
                },
                "chaos": _connection_drop_chaos(probability=1.0),
            },
        )

        with pytest.raises(httpx.HTTPError):
            httpx.get(f"{base_url}/drop-response", timeout=5.0)


def test_response_connection_drop_probability_zero_returns_complete_body():
    with _run_uvicorn(mock_app) as base_url:
        _create_stub(
            base_url,
            {
                "request": {"path": "/drop-response-none", "method": "GET"},
                "action": {
                    "response": {
                        "status_code": 200,
                        "headers": {"Content-Type": "text/plain"},
                        "body": "response-complete",
                    }
                },
                "chaos": _connection_drop_chaos(probability=0.0),
            },
        )

        response = httpx.get(f"{base_url}/drop-response-none", timeout=5.0)
        assert response.status_code == 200
        assert response.text == "response-complete"


def test_proxy_connection_drop_probability_one_interrupts_client():
    upstream = FastAPI()

    @upstream.get("/upstream")
    async def upstream_handler():
        return Response(content=b"proxied-body-for-drop", media_type="text/plain")

    with _run_uvicorn(upstream) as upstream_url:
        with _run_uvicorn(mock_app) as base_url:
            _create_stub(
                base_url,
                {
                    "request": {"path": "/drop-proxy", "method": "GET"},
                    "action": {"proxy": {"url": f"{upstream_url}/upstream"}},
                    "chaos": _connection_drop_chaos(probability=1.0),
                },
            )

            with pytest.raises(httpx.HTTPError):
                httpx.get(f"{base_url}/drop-proxy", timeout=5.0)


def test_proxy_connection_drop_probability_zero_returns_complete_body():
    upstream = FastAPI()

    @upstream.get("/upstream")
    async def upstream_handler():
        return Response(content=b"proxied-body-complete", media_type="text/plain")

    with _run_uvicorn(upstream) as upstream_url:
        with _run_uvicorn(mock_app) as base_url:
            _create_stub(
                base_url,
                {
                    "request": {"path": "/drop-proxy-none", "method": "GET"},
                    "action": {"proxy": {"url": f"{upstream_url}/upstream"}},
                    "chaos": _connection_drop_chaos(probability=0.0),
                },
            )

            response = httpx.get(f"{base_url}/drop-proxy-none", timeout=5.0)
            assert response.status_code == 200
            assert response.content == b"proxied-body-complete"


def test_sse_connection_drop_probability_one_interrupts_client():
    with _run_uvicorn(mock_app) as base_url:
        _create_stub(
            base_url,
            {
                "request": {"path": "/drop-sse", "method": "GET"},
                "action": {
                    "sse": {
                        "default_delay_ms": 0,
                        "events": [
                            {"id": "1", "event": "message", "data": "hello"},
                            {"id": "2", "event": "message", "data": "world"},
                        ],
                    }
                },
                "chaos": _connection_drop_chaos(probability=1.0),
            },
        )

        with pytest.raises(httpx.HTTPError):
            httpx.get(f"{base_url}/drop-sse", timeout=5.0)


def test_sse_connection_drop_probability_zero_returns_complete_stream():
    with _run_uvicorn(mock_app) as base_url:
        _create_stub(
            base_url,
            {
                "request": {"path": "/drop-sse-none", "method": "GET"},
                "action": {
                    "sse": {
                        "default_delay_ms": 0,
                        "events": [
                            {"id": "1", "event": "message", "data": "hello"},
                            {"id": "2", "event": "message", "data": "world"},
                        ],
                    }
                },
                "chaos": _connection_drop_chaos(probability=0.0),
            },
        )

        response = httpx.get(f"{base_url}/drop-sse-none", timeout=5.0)
        assert response.status_code == 200
        assert "data: hello" in response.text
        assert "data: world" in response.text
