from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from tests.conftest import _test_client_ctx

_AUTH = {
    "Authorization": "Bearer test-key-1",
    "Accept": "application/json, text/event-stream",
}
_DEEPL_ENV = {
    "DEEPL_API_KEY": "fake-key-abc123",
    "DEEPL_BLOB_CONTAINER": "test-container",
    "DEEPL_BLOB_OUTPUT_PREFIX": "deepl/translated/",
}


def _call(client: TestClient, session_id: str, tool: str, args: dict) -> str:
    """Call an MCP tool and return the raw response text (SSE format)."""
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        },
        headers={**_AUTH, "Mcp-Session-Id": session_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.text


@pytest.fixture
def deepl_client():
    with _test_client_ctx(**_DEEPL_ENV) as client:
        yield client


@pytest.fixture
def deepl_session(deepl_client: TestClient) -> str:
    resp = deepl_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        },
        headers=_AUTH,
    )
    assert resp.status_code == 200
    return resp.headers["mcp-session-id"]


@pytest.fixture(autouse=True)
def _reset_deepl_singleton():
    """Inject a fresh mock translator and reset the singleton after each test."""
    import mcp_server.utils.deepl_client as dc

    mock = MagicMock()
    dc._translator = mock
    yield mock
    dc._translator = None


# ── Tool registration ──────────────────────────────────────────────────────────


def test_deepl_tools_registered(deepl_client: TestClient, deepl_session: str):
    resp = deepl_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers={**_AUTH, "Mcp-Session-Id": deepl_session},
    )
    assert resp.status_code == 200
    body = resp.text
    for name in (
        "deepl_translate_text",
        "deepl_list_source_languages",
        "deepl_list_target_languages",
        "deepl_list_glossaries",
        "deepl_get_glossary_entries",
        "deepl_create_glossary",
        "deepl_delete_glossary",
        "deepl_translate_document",
    ):
        assert name in body, f"Tool '{name}' not found in tools/list response"


# ── deepl_translate_text ───────────────────────────────────────────────────────


def test_translate_text_happy_path(
    deepl_client: TestClient, deepl_session: str, _reset_deepl_singleton: MagicMock
):
    mock_result = MagicMock()
    mock_result.text = "Bonjour le monde"
    mock_result.detected_source_lang.code = "EN"
    mock_result.billed_characters = 11
    _reset_deepl_singleton.translate_text.return_value = mock_result

    body = _call(deepl_client, deepl_session, "deepl_translate_text", {
        "text": "Hello world",
        "target_lang": "FR",
    })

    assert "Bonjour le monde" in body
    assert "EN" in body


def test_translate_text_unconfigured_key():
    import mcp_server.utils.deepl_client as dc

    dc._translator = None  # force fresh init with empty key
    with _test_client_ctx(**{**_DEEPL_ENV, "DEEPL_API_KEY": ""}) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                             "clientInfo": {"name": "pytest", "version": "1.0"}}},
            headers=_AUTH,
        )
        session_id = resp.headers["mcp-session-id"]
        body = _call(client, session_id, "deepl_translate_text", {
            "text": "Hello",
            "target_lang": "FR",
        })
    assert "DEEPL_API_KEY" in body or "error" in body.lower() or "isError" in body


# ── deepl_list_source_languages ────────────────────────────────────────────────


def test_list_source_languages(
    deepl_client: TestClient, deepl_session: str, _reset_deepl_singleton: MagicMock
):
    mock_lang_en = MagicMock()
    mock_lang_en.code = "EN"
    mock_lang_en.name = "English"
    mock_lang_fr = MagicMock()
    mock_lang_fr.code = "FR"
    mock_lang_fr.name = "French"
    _reset_deepl_singleton.get_source_languages.return_value = [mock_lang_en, mock_lang_fr]

    body = _call(deepl_client, deepl_session, "deepl_list_source_languages", {})

    assert "EN" in body
    assert "FR" in body
    assert "count" in body


# ── deepl_list_glossaries ──────────────────────────────────────────────────────


def test_list_glossaries_empty(
    deepl_client: TestClient, deepl_session: str, _reset_deepl_singleton: MagicMock
):
    _reset_deepl_singleton.list_glossaries.return_value = []

    body = _call(deepl_client, deepl_session, "deepl_list_glossaries", {})

    assert "count" in body


# ── deepl_create_glossary ──────────────────────────────────────────────────────


def test_create_glossary(
    deepl_client: TestClient, deepl_session: str, _reset_deepl_singleton: MagicMock
):
    mock_glossary = MagicMock()
    mock_glossary.glossary_id = "gls-abc123"
    mock_glossary.name = "Test Glossary"
    mock_glossary.source_lang = "EN"
    mock_glossary.target_lang = "FR"
    mock_glossary.entry_count = 2
    mock_glossary.creation_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_glossary.ready = True
    _reset_deepl_singleton.create_glossary.return_value = mock_glossary

    body = _call(deepl_client, deepl_session, "deepl_create_glossary", {
        "name": "Test Glossary",
        "source_lang": "EN",
        "target_lang": "FR",
        "entries": {"Hello": "Bonjour", "Goodbye": "Au revoir"},
    })

    assert "gls-abc123" in body
    assert "Test Glossary" in body


# ── deepl_delete_glossary ──────────────────────────────────────────────────────


def test_delete_glossary(
    deepl_client: TestClient, deepl_session: str, _reset_deepl_singleton: MagicMock
):
    _reset_deepl_singleton.delete_glossary.return_value = None

    body = _call(deepl_client, deepl_session, "deepl_delete_glossary", {
        "glossary_id": "gls-abc123",
    })

    assert "gls-abc123" in body
    assert "true" in body.lower()


# ── deepl_translate_document — guard checks ────────────────────────────────────


def test_translate_document_unsupported_extension(
    deepl_client: TestClient, deepl_session: str
):
    body = _call(deepl_client, deepl_session, "deepl_translate_document", {
        "input_blob_path": "documents/file.txt",
        "target_lang": "FR",
    })
    assert "Unsupported" in body or "unsupported" in body or "isError" in body


def test_translate_document_missing_container():
    with _test_client_ctx(**{**_DEEPL_ENV, "DEEPL_BLOB_CONTAINER": ""}) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                             "clientInfo": {"name": "pytest", "version": "1.0"}}},
            headers=_AUTH,
        )
        session_id = resp.headers["mcp-session-id"]
        body = _call(client, session_id, "deepl_translate_document", {
            "input_blob_path": "documents/report.docx",
            "target_lang": "FR",
        })
    assert "DEEPL_BLOB_CONTAINER" in body or "isError" in body


# ── _derive_output_blob_path — unit tests ──────────────────────────────────────


def test_derive_output_blob_path_with_prefix():
    from mcp_server.tools.deepl.documents import _derive_output_blob_path

    assert _derive_output_blob_path("contracts/report.docx", "deepl/translated/") == \
        "deepl/translated/contracts/report.docx"


def test_derive_output_blob_path_no_prefix():
    from mcp_server.tools.deepl.documents import _derive_output_blob_path

    assert _derive_output_blob_path("contracts/report.docx", "") == \
        "contracts/report_translated.docx"


def test_derive_output_blob_path_trailing_slash_stripped():
    from mcp_server.tools.deepl.documents import _derive_output_blob_path

    assert _derive_output_blob_path("file.pdf", "output/deepl") == "output/deepl/file.pdf"
