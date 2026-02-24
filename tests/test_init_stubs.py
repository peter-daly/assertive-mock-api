import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import assertive_mock_api_server.app as app_module


def _write_init_stubs(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_preloads_stubs_from_init_file_generates_uuid_when_missing_id(
    monkeypatch, tmp_path: Path
):
    init_file = tmp_path / "stubs.json"
    _write_init_stubs(
        init_file,
        {
            "stubs": [
                {
                    "request": {"path": "/preloaded", "method": "GET"},
                    "action": {
                        "response": {
                            "status_code": 200,
                            "headers": {},
                            "body": "from-init",
                        }
                    },
                }
            ]
        },
    )

    monkeypatch.setattr(app_module, "INIT_STUBS_FILE", init_file)

    with TestClient(app_module.app) as client:
        stubs_response = client.get("/__mock__/stubs")
        assert stubs_response.status_code == 200
        stubs = stubs_response.json()["stubs"]
        assert len(stubs) == 1

        generated_id = stubs[0]["stub_id"]
        assert generated_id
        UUID(generated_id)

        request_response = client.get("/preloaded")
        assert request_response.status_code == 200
        assert request_response.text == "from-init"


def test_preloads_stubs_from_init_file_uses_explicit_id(monkeypatch, tmp_path: Path):
    init_file = tmp_path / "stubs.json"
    _write_init_stubs(
        init_file,
        {
            "stubs": [
                {
                    "id": "preloaded-id-1",
                    "request": {"path": "/preloaded-with-id", "method": "GET"},
                    "action": {
                        "response": {
                            "status_code": 200,
                            "headers": {},
                            "body": "with-id",
                        }
                    },
                }
            ]
        },
    )

    monkeypatch.setattr(app_module, "INIT_STUBS_FILE", init_file)

    with TestClient(app_module.app) as client:
        stubs_response = client.get("/__mock__/stubs")
        assert stubs_response.status_code == 200
        stubs = stubs_response.json()["stubs"]
        assert len(stubs) == 1
        assert stubs[0]["stub_id"] == "preloaded-id-1"

        request_response = client.get("/preloaded-with-id")
        assert request_response.status_code == 200
        assert request_response.text == "with-id"


def test_preloaded_stubs_reject_scope_field(monkeypatch, tmp_path: Path):
    init_file = tmp_path / "stubs.json"
    _write_init_stubs(
        init_file,
        {
            "stubs": [
                {
                    "id": "scoped-preload",
                    "scope": "team_a",
                    "request": {"path": "/scoped-preload", "method": "GET"},
                    "action": {
                        "response": {
                            "status_code": 200,
                            "headers": {},
                            "body": "x",
                        }
                    },
                }
            ]
        },
    )

    monkeypatch.setattr(app_module, "INIT_STUBS_FILE", init_file)

    with pytest.raises(RuntimeError, match="cannot define scope"):
        with TestClient(app_module.app):
            pass


def test_preloaded_stubs_support_chaos_latency(monkeypatch, tmp_path: Path):
    init_file = tmp_path / "stubs.json"
    _write_init_stubs(
        init_file,
        {
            "stubs": [
                {
                    "id": "chaos-preload",
                    "request": {"path": "/chaos-preload", "method": "GET"},
                    "action": {
                        "response": {
                            "status_code": 200,
                            "headers": {},
                            "body": "slow",
                        }
                    },
                    "chaos": {"latency": {"base_ms": 0, "jitter_ms": 0}},
                }
            ]
        },
    )

    monkeypatch.setattr(app_module, "INIT_STUBS_FILE", init_file)

    with TestClient(app_module.app) as client:
        stubs_response = client.get("/__mock__/stubs")
        assert stubs_response.status_code == 200
        stubs = stubs_response.json()["stubs"]
        assert len(stubs) == 1
        assert stubs[0]["stub_id"] == "chaos-preload"
        assert stubs[0]["chaos"]["latency"]["base_ms"] == 0
        assert stubs[0]["chaos"]["latency"]["jitter_ms"] == 0

        request_response = client.get("/chaos-preload")
        assert request_response.status_code == 200
        assert request_response.text == "slow"


def test_preloaded_stubs_reject_invalid_chaos(monkeypatch, tmp_path: Path):
    init_file = tmp_path / "stubs.json"
    _write_init_stubs(
        init_file,
        {
            "stubs": [
                {
                    "id": "invalid-chaos",
                    "request": {"path": "/invalid-chaos", "method": "GET"},
                    "action": {
                        "response": {
                            "status_code": 200,
                            "headers": {},
                            "body": "x",
                        }
                    },
                    "chaos": {"latency": {"base_ms": -1, "jitter_ms": 0}},
                }
            ]
        },
    )

    monkeypatch.setattr(app_module, "INIT_STUBS_FILE", init_file)

    with pytest.raises(RuntimeError, match="Invalid stub payload"):
        with TestClient(app_module.app):
            pass


def test_preloaded_stubs_support_nested_connection_drop_fault(
    monkeypatch, tmp_path: Path
):
    init_file = tmp_path / "stubs.json"
    _write_init_stubs(
        init_file,
        {
            "stubs": [
                {
                    "id": "chaos-drop-preload",
                    "request": {"path": "/chaos-drop-preload", "method": "GET"},
                    "action": {
                        "response": {
                            "status_code": 200,
                            "headers": {},
                            "body": "maybe-drop",
                        }
                    },
                    "chaos": {
                        "faults": {"connection_drop": {"probability": 0.0}},
                    },
                }
            ]
        },
    )

    monkeypatch.setattr(app_module, "INIT_STUBS_FILE", init_file)

    with TestClient(app_module.app) as client:
        stubs_response = client.get("/__mock__/stubs")
        assert stubs_response.status_code == 200
        stubs = stubs_response.json()["stubs"]
        assert len(stubs) == 1
        assert stubs[0]["chaos"]["faults"]["connection_drop"]["probability"] == 0.0


def test_preloaded_stubs_rejects_top_level_connection_drop_fault(
    monkeypatch, tmp_path: Path
):
    init_file = tmp_path / "stubs.json"
    _write_init_stubs(
        init_file,
        {
            "stubs": [
                {
                    "id": "chaos-drop-invalid-shape",
                    "request": {
                        "path": "/chaos-drop-invalid-shape",
                        "method": "GET",
                    },
                    "action": {
                        "response": {
                            "status_code": 200,
                            "headers": {},
                            "body": "x",
                        }
                    },
                    "chaos": {"connection_drop": {"probability": 1.0}},
                }
            ]
        },
    )

    monkeypatch.setattr(app_module, "INIT_STUBS_FILE", init_file)

    with pytest.raises(RuntimeError, match="chaos.faults.connection_drop"):
        with TestClient(app_module.app):
            pass
