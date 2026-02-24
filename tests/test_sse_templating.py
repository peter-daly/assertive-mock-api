import pytest

from assertive_mock_api_server.core import (
    MockApiRequest,
    SseEvent,
    render_sse_event_templates,
)
from assertive_mock_api_server.templating import TemplateRenderError


def test_render_sse_event_templates_renders_data_id_and_event():
    request = MockApiRequest(
        path="/stream",
        method="GET",
        headers={},
        body="",
        host="localhost",
        query={"room": "alpha", "id": "evt-7"},
    )
    event = SseEvent(
        data="room={{ request.query.room }}",
        event="evt-{{ request.query.room }}",
        id="{{ request.query.id }}",
    )

    rendered = render_sse_event_templates(event, request)

    assert rendered.data == "room=alpha"
    assert rendered.event == "evt-alpha"
    assert rendered.id == "evt-7"


def test_render_sse_event_templates_propagates_template_errors():
    request = MockApiRequest(
        path="/stream",
        method="GET",
        headers={},
        body="",
        host="localhost",
        query={},
    )
    event = SseEvent(data="missing={{ request.query.room }}")

    with pytest.raises(TemplateRenderError):
        render_sse_event_templates(event, request)
