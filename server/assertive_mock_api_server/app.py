from contextlib import asynccontextmanager

from clean_ioc.ext.fastapi import Resolve, add_container_to_app
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from assertive_mock_api_server.container import get_container
from assertive_mock_api_server.core import (
    MockApiRequest,
    MockApiServer,
    ScopeAlreadyExistsError,
    ScopeNotFoundError,
    ScopeRepository,
)
from assertive_mock_api_server.payloads import (
    ApiAssertionPayload,
    CreateScopePayload,
    MockApiRequestListViewPayload,
    StubListViewPayload,
    StubPayload,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = get_container()
    async with add_container_to_app(app, container):
        yield


app = FastAPI(
    title="Assertive Mock API Server",
    description="A mock API server for testing.",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
    redoc_url=None,
)


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
                "/__mock__/stubs",
                "/__mock__/assert",
                "/__mock__/requests",
            ],
        },
        status_code=200,
        headers={"Content-Type": "application/json"},
    )


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

    api_response = await mock_server.handle_request(api_request)

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
