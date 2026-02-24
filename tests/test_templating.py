import pytest

from assertive_mock_api_server.core import MockApiRequest
from assertive_mock_api_server.templating import (
    TemplateRenderError,
    build_template_context,
    render_template,
)


def test_render_template_with_query_and_header_fields():
    request = MockApiRequest(
        path="/hello",
        method="GET",
        headers={"content-type": "text/plain", "x-request-id": "abc-123"},
        body="raw body",
        host="localhost",
        query={"name": "Peter"},
    )

    rendered = render_template(
        "Hello {{ request.query.name }} id={{ request.headers['x-request-id'] }}",
        request,
    )

    assert rendered == "Hello Peter id=abc-123"


def test_build_template_context_parses_json_body_when_content_type_is_json():
    request = MockApiRequest(
        path="/json",
        method="POST",
        headers={"content-type": "application/json; charset=utf-8"},
        body='{"user":{"id":"u_1"}}',
        host="localhost",
        query={},
    )

    context = build_template_context(request)

    assert context["request"]["body"]["user"]["id"] == "u_1"


def test_build_template_context_includes_path_params():
    request = MockApiRequest(
        path="/users/u_1",
        method="GET",
        headers={},
        body="",
        host="localhost",
        query={},
        path_params={"id": "u_1"},
    )

    context = build_template_context(request)

    assert context["request"]["path_params"] == {"id": "u_1"}


def test_build_template_context_keeps_raw_body_for_non_json_content_type():
    request = MockApiRequest(
        path="/text",
        method="POST",
        headers={"content-type": "text/plain"},
        body="plain text",
        host="localhost",
        query={},
    )

    context = build_template_context(request)

    assert context["request"]["body"] == "plain text"


def test_build_template_context_raises_for_invalid_json_when_content_type_is_json():
    request = MockApiRequest(
        path="/broken",
        method="POST",
        headers={"content-type": "application/json"},
        body='{"user":',
        host="localhost",
        query={},
    )

    with pytest.raises(
        TemplateRenderError,
        match="Invalid JSON request body for JSON content-type",
    ):
        build_template_context(request)
