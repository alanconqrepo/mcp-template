from starlette.testclient import TestClient


_AUTH = {"Authorization": "Bearer test-key-1", "Accept": "application/json, text/event-stream"}


def test_tools_list_includes_expected_tools(test_client: TestClient, mcp_session: str) -> None:
    """MCP tools/list should include ping and text_summary."""
    response = test_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers={**_AUTH, "Mcp-Session-Id": mcp_session},
    )
    assert response.status_code == 200
    body = response.text
    assert "ping" in body
    assert "text_summary" in body


def test_ping_tool_returns_pong(test_client: TestClient, mcp_session: str) -> None:
    """Call the ping tool and verify the pong response."""
    response = test_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "ping", "arguments": {}},
        },
        headers={**_AUTH, "Mcp-Session-Id": mcp_session},
    )
    assert response.status_code == 200
    assert "pong" in response.text


def test_ping_response_has_timestamp(test_client: TestClient, mcp_session: str) -> None:
    response = test_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "ping", "arguments": {}},
        },
        headers={**_AUTH, "Mcp-Session-Id": mcp_session},
    )
    assert response.status_code == 200
    assert "timestamp" in response.text


def test_text_summary_tool(test_client: TestClient, mcp_session: str) -> None:
    """text_summary truncates content and returns metadata."""
    response = test_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "text_summary",
                "arguments": {"content": "Hello world! " * 50, "max_length": 20},
            },
        },
        headers={**_AUTH, "Mcp-Session-Id": mcp_session},
    )
    assert response.status_code == 200
    body = response.text
    assert "summary" in body
    assert "word_count" in body
    assert "truncated" in body
