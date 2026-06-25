from __future__ import annotations

import httpx


def get_openwebui_client() -> httpx.AsyncClient:
    """Return a configured AsyncClient for OpenWebUI. Raises RuntimeError if URL is not set."""
    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.OPENWEBUI_URL:
        raise RuntimeError(
            "OPENWEBUI_URL is not configured. Set the OPENWEBUI_URL environment variable."
        )
    if not settings.OPENWEBUI_API_KEY:
        raise RuntimeError(
            "OPENWEBUI_API_KEY is not configured. Set the OPENWEBUI_API_KEY environment variable."
        )
    return httpx.AsyncClient(
        base_url=settings.OPENWEBUI_URL,
        headers={"Authorization": f"Bearer {settings.OPENWEBUI_API_KEY}"},
        timeout=float(settings.OPENWEBUI_TIMEOUT),
    )


async def raise_for_status(response: httpx.Response) -> None:
    """Raise a descriptive RuntimeError on HTTP error responses."""
    if response.is_error:
        try:
            body = response.text
        except Exception:
            body = "<unreadable>"
        raise RuntimeError(f"OpenWebUI API error {response.status_code}: {body}")
