from __future__ import annotations

import httpx


def get_outline_client() -> httpx.AsyncClient:
    """Return a configured AsyncClient for the Outline REST API."""
    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.OUTLINE_URL:
        raise RuntimeError("OUTLINE_URL is not configured")
    if not settings.OUTLINE_API_TOKEN:
        raise RuntimeError("OUTLINE_API_TOKEN is not configured")

    return httpx.AsyncClient(
        base_url=settings.OUTLINE_URL.rstrip("/") + "/api/",
        headers={
            "Authorization": f"Bearer {settings.OUTLINE_API_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


async def outline_post(client: httpx.AsyncClient, endpoint: str, body: dict) -> dict:
    """POST to an Outline API endpoint, raise on HTTP or API errors, return the full response."""
    payload = {k: v for k, v in body.items() if v is not None}
    response = await client.post(endpoint, json=payload)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok", True):
        raise RuntimeError(
            f"Outline API error on {endpoint}: {data.get('error')} (status {data.get('status')})"
        )
    return data
