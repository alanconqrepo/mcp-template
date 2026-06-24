from __future__ import annotations

import httpx


def get_prefect_client() -> httpx.AsyncClient:
    """Return a configured AsyncClient for the Prefect REST API."""
    from mcp_server.config import get_settings

    settings = get_settings()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.PREFECT_API_KEY:
        headers["Authorization"] = f"Bearer {settings.PREFECT_API_KEY}"

    base_url = settings.PREFECT_URL.rstrip("/") + "/"
    return httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30.0)


async def raise_for_status(response: httpx.Response) -> None:
    """Raise a descriptive RuntimeError on HTTP error responses."""
    if response.is_error:
        try:
            body = response.text
        except Exception:
            body = "<unreadable>"
        raise RuntimeError(f"Prefect API error {response.status_code}: {body}")
