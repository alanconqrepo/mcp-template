from __future__ import annotations

import httpx


def get_baserow_client() -> httpx.AsyncClient:
    """Return a configured AsyncClient for Baserow. Raises RuntimeError if token is not set."""
    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.BASEROW_TOKEN:
        raise RuntimeError(
            "BASEROW_TOKEN is not configured. Set the BASEROW_TOKEN environment variable."
        )
    return httpx.AsyncClient(
        base_url=settings.BASEROW_URL,
        headers={"Authorization": f"Token {settings.BASEROW_TOKEN}"},
        timeout=30.0,
    )


async def raise_for_status(response: httpx.Response) -> None:
    """Raise a descriptive RuntimeError on HTTP error responses."""
    if response.is_error:
        try:
            body = response.text
        except Exception:
            body = "<unreadable>"
        raise RuntimeError(f"Baserow API error {response.status_code}: {body}")
