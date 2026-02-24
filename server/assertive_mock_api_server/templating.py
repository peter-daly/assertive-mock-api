import json
from typing import Any, TYPE_CHECKING

from jinja2 import Environment, StrictUndefined, TemplateError

if TYPE_CHECKING:
    from .core import MockApiRequest


class TemplateRenderError(ValueError):
    pass


_jinja_env = Environment(
    undefined=StrictUndefined,
    autoescape=False,
)


def _find_header_value(headers: dict[Any, Any], key: str) -> str | None:
    for header_key, value in headers.items():
        if str(header_key).lower() == key:
            return str(value)
    return None


def _is_json_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return False

    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _parse_smart_body(request: "MockApiRequest") -> Any:
    content_type = _find_header_value(request.headers, "content-type")
    if not _is_json_content_type(content_type):
        return request.body

    body_value = request.body
    if isinstance(body_value, bytes):
        try:
            raw_json = body_value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TemplateRenderError(
                "Invalid JSON request body for JSON content-type"
            ) from error
    else:
        raw_json = str(body_value)

    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise TemplateRenderError(
            "Invalid JSON request body for JSON content-type"
        ) from error


def build_template_context(request: "MockApiRequest") -> dict[str, Any]:
    return {
        "request": {
            "path": request.path,
            "method": request.method,
            "host": request.host,
            "scope": request.scope,
            "query": request.query,
            "headers": request.headers,
            "body": _parse_smart_body(request),
        }
    }


def render_template(template: str, request: "MockApiRequest") -> str:
    context = build_template_context(request)

    try:
        return _jinja_env.from_string(template).render(context)
    except TemplateError as error:
        raise TemplateRenderError(str(error)) from error
