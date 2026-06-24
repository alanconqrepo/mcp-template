from tests.conftest import _test_client_ctx


def test_valid_api_key_reaches_mcp() -> None:
    with _test_client_ctx() as client:
        response = client.get("/mcp", headers={"Authorization": "Bearer test-key-1"})
    # Auth passed — any non-401 status is fine (MCP uses GET for SSE streams)
    assert response.status_code != 401


def test_missing_api_key_returns_401() -> None:
    with _test_client_ctx() as client:
        response = client.get("/mcp")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_invalid_api_key_returns_401() -> None:
    with _test_client_ctx() as client:
        response = client.get("/mcp", headers={"Authorization": "Bearer wrong-key"})
    assert response.status_code == 401


def test_auth_mode_none_no_auth_required() -> None:
    with _test_client_ctx(AUTH_MODE="none") as client:
        response = client.get("/mcp")
    # No auth = endpoint reachable (any non-401 is acceptable)
    assert response.status_code != 401


def test_health_always_public() -> None:
    """Health endpoint requires no auth regardless of mode."""
    with _test_client_ctx() as client:
        response = client.get("/health")
    assert response.status_code == 200
