from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

# pyodbc requires a native ODBC driver that is not available in all environments.
# Mock it at the module level so the SQL tools can be imported without the driver.
if "pyodbc" not in sys.modules:
    sys.modules["pyodbc"] = MagicMock()

# fastmcp.Image was removed in fastmcp>=3.x — mock it so playwright tools can import.
import fastmcp as _fastmcp
if not hasattr(_fastmcp, "Image"):
    _fastmcp.Image = MagicMock()

_TEST_ENV_DEFAULTS = {
    "AUTH_MODE": "api_key",
    "API_KEYS": '["test-key-1"]',
    "LANGFUSE_ENABLED": "false",
    "MCP_SERVER_NAME": "test-mcp-server",
    "MCP_MOUNT_PATH": "/mcp",
}


@contextmanager
def _test_client_ctx(**env_overrides):
    """Context manager that sets env vars, creates a TestClient, and cleans up after."""
    from mcp_server.config import get_settings

    env = {**_TEST_ENV_DEFAULTS, **env_overrides}
    old_env = {k: os.environ.get(k) for k in env}

    for k, v in env.items():
        os.environ[k] = v
    get_settings.cache_clear()

    try:
        from mcp_server.app import create_app

        with TestClient(create_app(), raise_server_exceptions=True) as client:
            yield client
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


@pytest.fixture
def test_client() -> TestClient:
    """Default test client: api_key auth, test-key-1, Langfuse disabled."""
    with _test_client_ctx() as client:
        yield client


@pytest.fixture
def mcp_session(test_client: TestClient) -> str:
    """Initialize an MCP session and return the session ID."""
    response = test_client.post(
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
        headers={
            "Authorization": "Bearer test-key-1",
            "Accept": "application/json, text/event-stream",
        },
    )
    assert response.status_code == 200, f"MCP init failed: {response.text}"
    session_id = response.headers.get("mcp-session-id")
    assert session_id, "No session ID returned"
    return session_id
