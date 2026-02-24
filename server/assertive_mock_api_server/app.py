import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from clean_ioc.ext.fastapi import Resolve, add_container_to_app
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates

from assertive_mock_api_server.container import get_container
from assertive_mock_api_server.core import (
    SseEvent,
    MockApiSseResponse,
    MockApiRequest,
    MockApiServer,
    ScopeAlreadyExistsError,
    ScopeNotFoundError,
    ScopeRepository,
    encode_sse_event,
    resolve_sse_delay_ms,
)
from assertive_mock_api_server.payloads import (
    ApiAssertionPayload,
    CreateScopePayload,
    MockApiRequestListViewPayload,
    StubListViewPayload,
    StubPayload,
)
from assertive_mock_api_server.templating import TemplateRenderError

INIT_STUBS_FILE = Path("/etc/init.d/stubs.json")


def _extract_init_stub_entries(raw_data: Any) -> list[dict[str, Any]]:
    if isinstance(raw_data, list):
        entries = raw_data
    elif isinstance(raw_data, dict) and isinstance(raw_data.get("stubs"), list):
        entries = raw_data["stubs"]
    else:
        raise ValueError("stubs.json must be a list or an object with a 'stubs' list")

    parsed_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"stubs.json entry {index} must be an object")
        parsed_entries.append(entry)
    return parsed_entries


async def _load_init_stubs(container) -> None:
    if not INIT_STUBS_FILE.exists():
        return

    raw_content = INIT_STUBS_FILE.read_text(encoding="utf-8")
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Invalid JSON in {INIT_STUBS_FILE}") from error

    entries = _extract_init_stub_entries(parsed)
    mock_server: MockApiServer = await container.resolve_async(MockApiServer)
    for index, entry in enumerate(entries, start=1):
        payload_data = dict(entry)
        explicit_stub_id = payload_data.pop("stub_id", None)
        if explicit_stub_id is None:
            explicit_stub_id = payload_data.pop("id", None)

        if "scope" in payload_data:
            raise RuntimeError(
                f"Invalid stubs.json entry {index}: preloaded stubs cannot define scope"
            )

        try:
            payload = StubPayload.model_validate(payload_data)
        except Exception as error:
            raise RuntimeError(
                f"Invalid stub payload in {INIT_STUBS_FILE} at entry {index}"
            ) from error

        stub = payload.to_stub(scope=None)
        if explicit_stub_id is not None:
            normalized_id = str(explicit_stub_id).strip()
            if not normalized_id:
                raise RuntimeError(
                    f"Invalid stub id for stubs.json entry {index}: id cannot be empty"
                )
            stub.stub_id = normalized_id

        await mock_server.add_stub(stub)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = get_container()
    async with add_container_to_app(app, container):
        await _load_init_stubs(container)
        yield


app = FastAPI(
    title="Assertive Mock API Server",
    description="A mock API server for testing.",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
    redoc_url=None,
)
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))
POLL_INTERVAL = "3s"


async def extract_body(request: Request) -> str | bytes:
    """
    Extract the body from the request and return as string if possible, otherwise bytes.

    Args:
        request: The FastAPI request object

    Returns:
        The body content as string if decodable, otherwise as bytes
    """
    body_bytes = await request.body()

    # Return empty string if no body
    if not body_bytes:
        return ""

    # Try to decode as UTF-8 string
    try:
        return body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # Return raw bytes if can't be decoded
        return body_bytes


def resolve_scope_from_headers(
    headers: dict, scope_repository: ScopeRepository
) -> str | None:
    matches = scope_repository.resolve_from_headers(headers)

    if len(matches) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple scope headers matched this request",
        )

    if len(matches) == 1:
        return matches[0]

    return None


async def _admin_context(mock_server) -> dict[str, Any]:
    stubs = await mock_server.list_stubs()
    requests = await mock_server.list_requests()
    scopes = await mock_server.list_scopes()
    recent_requests = list(reversed(requests))[:100]
    return {
        "stubs": StubListViewPayload.from_stubs(stubs).stubs,
        "requests": MockApiRequestListViewPayload.from_mock_api_requests(
            recent_requests
        ).requests,
        "scopes": scopes,
        "poll_interval": POLL_INTERVAL,
    }


async def _list_all_stubs(mock_server) -> list:
    global_stubs = await mock_server.list_stubs()
    scopes = await mock_server.list_scopes()
    scoped_stubs: list = []
    for scope in scopes:
        scoped_stubs.extend(await mock_server.list_stubs(scope))

    # Keep insertion order while deduplicating by stub_id.
    by_id: dict[str, Any] = {}
    for stub in global_stubs + scoped_stubs:
        by_id[stub.stub_id] = stub
    return list(by_id.values())


async def _render_stubs_partial(
    request: Request, mock_server, *, error: str | None = None, status_code: int = 200
) -> HTMLResponse:
    context = await _admin_context(mock_server)
    context.update({"request": request, "error": error})
    return templates.TemplateResponse(
        request=request,
        name="admin/_stubs.html",
        context=context,
        status_code=status_code,
    )


async def _render_requests_partial(
    request: Request, mock_server, *, error: str | None = None, status_code: int = 200
) -> HTMLResponse:
    context = await _admin_context(mock_server)
    context.update({"request": request, "error": error})
    return templates.TemplateResponse(
        request=request,
        name="admin/_requests.html",
        context=context,
        status_code=status_code,
    )


async def _render_scopes_partial(
    request: Request, mock_server, *, error: str | None = None, status_code: int = 200
) -> HTMLResponse:
    context = await _admin_context(mock_server)
    context.update({"request": request, "error": error})
    return templates.TemplateResponse(
        request=request,
        name="admin/_scopes.html",
        context=context,
        status_code=status_code,
    )


# --- Endpoints ---


@app.post("/__mock__/scopes", status_code=201)
async def create_scope(
    payload: CreateScopePayload,
    mock_server=Resolve(MockApiServer),
):
    try:
        scope = await mock_server.create_scope(payload.name)
    except ScopeAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {"success": True, "name": scope}


@app.delete("/__mock__/scopes/{name}")
async def delete_scope(name: str, mock_server=Resolve(MockApiServer)):
    try:
        deleted_scope = await mock_server.delete_scope(name)
    except ScopeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {"success": True, "name": deleted_scope}


@app.post("/__mock__/stubs")
async def add_stub(
    stub_payload: StubPayload,
    request: Request,
    mock_server=Resolve(MockApiServer),
    scope_repository=Resolve(ScopeRepository),
):
    scope = resolve_scope_from_headers(dict(request.headers), scope_repository)
    await mock_server.add_stub(stub_payload.to_stub(scope=scope))
    return {"success": True}


@app.post("/__mock__/assert")
async def assert_request(
    assertion: ApiAssertionPayload,
    request: Request,
    mock_server=Resolve(MockApiServer),
    scope_repository=Resolve(ScopeRepository),
):
    """
    Assert that the request matches the given assertion.
    """
    scope = resolve_scope_from_headers(dict(request.headers), scope_repository)
    result = await mock_server.confirm_assertion(assertion.to_api_assertion(), scope)

    return {"result": result.success}


@app.get("/__mock__/requests")
async def list_requests(
    request: Request,
    mock_server=Resolve(MockApiServer),
    scope_repository=Resolve(ScopeRepository),
):
    """
    List all requests that match the given assertion.
    """
    scope = resolve_scope_from_headers(dict(request.headers), scope_repository)
    result = await mock_server.list_requests(scope)

    return MockApiRequestListViewPayload.from_mock_api_requests(result)


@app.get("/__mock__/stubs")
async def list_stubs(
    request: Request,
    mock_server=Resolve(MockApiServer),
    scope_repository=Resolve(ScopeRepository),
):
    """
    List all stubs.
    """
    scope = resolve_scope_from_headers(dict(request.headers), scope_repository)
    stubs = await mock_server.list_stubs(scope)
    stub_views = StubListViewPayload.from_stubs(stubs)

    return stub_views


@app.delete("/__mock__/stubs/{stub_id}")
async def delete_stub(
    stub_id: str,
    request: Request,
    mock_server=Resolve(MockApiServer),
    scope_repository=Resolve(ScopeRepository),
):
    scope = resolve_scope_from_headers(dict(request.headers), scope_repository)
    deleted = await mock_server.delete_stub(stub_id, scope)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Stub '{stub_id}' was not found")
    return {"success": True, "stub_id": stub_id}


@app.get("/__mock__/scopes")
async def list_scopes(mock_server=Resolve(MockApiServer)):
    scopes = await mock_server.list_scopes()
    return {"scopes": scopes}


@app.api_route(
    "/__mock__",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def mock_api_root(request: Request):
    """
    Root endpoint for the mock API server.
    """
    return JSONResponse(
        content={
            "message": "Welcome to the Assertive Mock API Server!",
            "available_endpoints": [
                "/__mock__/scopes",
                "/__mock__/scopes (GET list)",
                "/__mock__/stubs",
                "/__mock__/stubs/{stub_id}",
                "/__mock__/assert",
                "/__mock__/requests",
                "/__admin__",
            ],
        },
        status_code=200,
        headers={"Content-Type": "application/json"},
    )


@app.get("/__admin__", response_class=HTMLResponse)
async def admin_index(
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    context = await _admin_context(mock_server)
    context.update({"request": request})
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context=context,
    )


@app.get("/__admin__/stubs/new", response_class=HTMLResponse)
async def admin_new_stub(
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    context = await _admin_context(mock_server)
    context.update(
        {
            "request": request,
            "error": None,
            "success": None,
            "form_data": {},
        }
    )
    return templates.TemplateResponse(
        request=request,
        name="admin/stub_create.html",
        context=context,
    )


@app.get("/__admin__/stubs/{stub_id}", response_class=HTMLResponse)
async def admin_stub_detail(
    stub_id: str,
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    stubs = await _list_all_stubs(mock_server)
    target_stub = next((stub for stub in stubs if stub.stub_id == stub_id), None)
    if target_stub is None:
        raise HTTPException(status_code=404, detail=f"Stub '{stub_id}' was not found")

    context = await _admin_context(mock_server)
    context.update(
        {
            "request": request,
            "stub": StubListViewPayload.from_stubs([target_stub]).stubs[0],
        }
    )
    return templates.TemplateResponse(
        request=request,
        name="admin/stub_detail.html",
        context=context,
    )


@app.get("/__admin__/scopes/{name}", response_class=HTMLResponse)
async def admin_scope_detail(
    name: str,
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    scopes = await mock_server.list_scopes()
    normalized_name = name.lower()
    if normalized_name not in scopes:
        raise HTTPException(status_code=404, detail=f"Scope '{name}' was not found")

    scoped_stubs = await mock_server.list_stubs(normalized_name)
    scoped_requests = await mock_server.list_requests(normalized_name)

    context = await _admin_context(mock_server)
    context.update(
        {
            "request": request,
            "scope_name": normalized_name,
            "stubs": StubListViewPayload.from_stubs(scoped_stubs).stubs,
            "requests": MockApiRequestListViewPayload.from_mock_api_requests(
                list(reversed(scoped_requests))[:100]
            ).requests,
        }
    )
    return templates.TemplateResponse(
        request=request,
        name="admin/scope_detail.html",
        context=context,
    )


@app.get("/__admin__/partials/stubs", response_class=HTMLResponse)
async def admin_partial_stubs(
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    return await _render_stubs_partial(request, mock_server)


@app.get("/__admin__/partials/requests", response_class=HTMLResponse)
async def admin_partial_requests(
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    return await _render_requests_partial(request, mock_server)


@app.get("/__admin__/partials/scopes", response_class=HTMLResponse)
async def admin_partial_scopes(
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    return await _render_scopes_partial(request, mock_server)


@app.delete("/__admin__/actions/stubs/{stub_id}", response_class=HTMLResponse)
async def admin_delete_stub(
    stub_id: str,
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    deleted = await mock_server.delete_stub(stub_id, scope=None)
    if not deleted:
        return await _render_stubs_partial(
            request,
            mock_server,
            error=f"Stub '{stub_id}' was not found",
            status_code=404,
        )
    return await _render_stubs_partial(request, mock_server)


@app.delete("/__admin__/actions/scopes/{name}", response_class=HTMLResponse)
async def admin_delete_scope(
    name: str,
    request: Request,
    mock_server=Resolve(MockApiServer),
):
    try:
        await mock_server.delete_scope(name)
    except ScopeNotFoundError as error:
        return await _render_scopes_partial(
            request,
            mock_server,
            error=str(error),
            status_code=404,
        )
    return await _render_scopes_partial(request, mock_server)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def catch_all(
    request: Request,
    mock_server=Resolve(MockApiServer),
    scope_repository=Resolve(ScopeRepository),
):
    """
    Catch-all endpoint for all requests.
    """
    headers = dict(request.headers)
    scope = resolve_scope_from_headers(headers, scope_repository)
    query = dict(request.query_params)
    method = request.method
    body = await extract_body(request)
    hostname = request.url.hostname or ""
    path = request.url.path

    api_request = MockApiRequest(
        method=method,
        path=path,
        query=query,
        headers=headers,
        body=body,
        host=hostname,
        scope=scope,
    )

    try:
        api_response = await mock_server.handle_request(api_request)
    except TemplateRenderError as error:
        return JSONResponse(
            status_code=500,
            content={
                "error": "TEMPLATE_RENDER_ERROR",
                "detail": str(error),
            },
        )

    if isinstance(api_response, MockApiSseResponse):

        async def stream_events():
            event: SseEvent
            for event in api_response.events:
                delay_ms = resolve_sse_delay_ms(event, api_response.default_delay_ms)
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000)
                yield encode_sse_event(event).encode("utf-8")

        return StreamingResponse(
            stream_events(),
            status_code=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
            media_type="text/event-stream",
        )

    # Convert MockApiResponse to FastAPI response
    content = api_response.body
    status_code = api_response.status_code
    response_headers = api_response.headers

    # Choose response type based on content
    if isinstance(content, dict) or isinstance(content, list):
        return JSONResponse(
            content=content,
            status_code=status_code,
            headers=response_headers,
        )
    if isinstance(content, str):
        return Response(
            content=content, status_code=status_code, headers=response_headers
        )
    if isinstance(content, bytes):
        return Response(
            content=content,
            status_code=status_code,
            headers=response_headers,
            media_type="application/octet-stream",
        )

    # For None or other types
    return Response(status_code=status_code, headers=response_headers)
