from __future__ import annotations

import httpx


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts via an OpenAI-compatible /v1/embeddings endpoint.
    Requests are batched according to EMBEDDING_BATCH_SIZE.
    """
    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.EMBEDDING_API_KEY:
        raise RuntimeError(
            "EMBEDDING_API_KEY is not configured. "
            "Set it to your embedding API key (OpenAI, Azure OpenAI, Ollama, …)."
        )

    all_embeddings: list[list[float]] = []
    batch_size = settings.EMBEDDING_BATCH_SIZE
    headers = {
        "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(
        base_url=settings.EMBEDDING_BASE_URL.rstrip("/"),
        headers=headers,
        timeout=float(settings.EMBEDDING_TIMEOUT),
    ) as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await client.post(
                "/embeddings",
                json={"model": settings.EMBEDDING_MODEL, "input": batch},
            )
            if response.is_error:
                raise RuntimeError(
                    f"Embedding API error {response.status_code}: {response.text}"
                )
            data = response.json()
            sorted_items = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend(item["embedding"] for item in sorted_items)

    return all_embeddings
