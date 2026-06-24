from __future__ import annotations

import httpx


async def graphql(query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL query/mutation against the Wiki.js instance."""
    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.WIKIJS_URL:
        raise RuntimeError("WIKIJS_URL is not configured")
    if not settings.WIKIJS_API_TOKEN:
        raise RuntimeError("WIKIJS_API_TOKEN is not configured")

    url = f"{settings.WIKIJS_URL.rstrip('/')}/graphql"
    headers = {
        "Authorization": f"Bearer {settings.WIKIJS_API_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json={"query": query, "variables": variables or {}},
            headers=headers,
        )
        response.raise_for_status()

    data = response.json()
    if errors := data.get("errors"):
        messages = "; ".join(e.get("message", str(e)) for e in errors)
        raise RuntimeError(f"Wiki.js GraphQL error: {messages}")

    return data.get("data", {})
