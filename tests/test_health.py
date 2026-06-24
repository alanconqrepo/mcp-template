from starlette.testclient import TestClient


def test_health_returns_200(test_client: TestClient) -> None:
    response = test_client.get("/health")
    assert response.status_code == 200


def test_health_response_shape(test_client: TestClient) -> None:
    data = test_client.get("/health").json()
    assert data["status"] == "ok"
    assert "server_name" in data
    assert "auth_mode" in data
    assert isinstance(data["tools_count"], int)
    assert isinstance(data["langfuse_enabled"], bool)


def test_health_no_auth_required(test_client: TestClient) -> None:
    """Health endpoint must be accessible without any Authorization header."""
    response = test_client.get("/health")
    assert response.status_code == 200


def test_health_reports_correct_tool_count(test_client: TestClient) -> None:
    data = test_client.get("/health").json()
    # Template ships with ping + text_summary
    assert data["tools_count"] >= 2
