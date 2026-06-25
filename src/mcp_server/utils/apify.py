from __future__ import annotations

import httpx

from mcp_server.config import get_settings


async def run_apify_actor(actor_id: str, input_data: dict, timeout: int = 300) -> list[dict]:
    """Run an Apify actor synchronously and return its dataset items."""
    settings = get_settings()
    if not settings.APIFY_API_TOKEN:
        raise RuntimeError("APIFY_API_TOKEN is not configured")

    headers = {"Authorization": f"Bearer {settings.APIFY_API_TOKEN}"}

    async with httpx.AsyncClient(timeout=timeout + 30) as client:
        run_resp = await client.post(
            f"https://api.apify.com/v2/acts/{actor_id}/runs",
            headers=headers,
            json=input_data,
            params={"waitForFinish": timeout},
        )
        run_resp.raise_for_status()
        dataset_id = run_resp.json()["data"]["defaultDatasetId"]

        items_resp = await client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            headers=headers,
            params={"format": "json"},
        )
        items_resp.raise_for_status()
        return items_resp.json()
