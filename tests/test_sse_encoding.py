from assertive_mock_api_server.core import (
    SseEvent,
    encode_sse_event,
    resolve_sse_delay_ms,
)


def test_encode_sse_event_with_optional_fields():
    event = SseEvent(
        id="evt-1",
        event="message",
        retry=5000,
        data="hello",
    )

    encoded = encode_sse_event(event)

    assert encoded == "id: evt-1\nevent: message\nretry: 5000\ndata: hello\n\n"


def test_encode_sse_event_with_multiline_data():
    event = SseEvent(data="line-1\nline-2")

    encoded = encode_sse_event(event)

    assert encoded == "data: line-1\ndata: line-2\n\n"


def test_resolve_sse_delay_ms_prefers_event_override():
    event = SseEvent(data="x", delay_ms=250)

    assert resolve_sse_delay_ms(event, default_delay_ms=1000) == 250


def test_resolve_sse_delay_ms_uses_default_when_event_override_missing():
    event = SseEvent(data="x")

    assert resolve_sse_delay_ms(event, default_delay_ms=1000) == 1000
