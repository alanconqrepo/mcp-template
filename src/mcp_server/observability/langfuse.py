from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)

_client: Any = None
_initialized: bool = False


def get_langfuse() -> Any | None:
    """Return the Langfuse singleton client, or None if disabled/unconfigured."""
    global _client, _initialized
    if _initialized:
        return _client
    _initialized = True

    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.LANGFUSE_ENABLED:
        return None
    if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
        logger.warning("Langfuse enabled but credentials missing — tracing disabled")
        return None

    try:
        from langfuse import Langfuse

        _client = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Langfuse client initialized")
    except Exception:
        logger.exception("Failed to initialize Langfuse client — tracing disabled")
        _client = None

    return _client


def shutdown_langfuse() -> None:
    """Flush and shut down the Langfuse client on server shutdown."""
    global _client
    if _client is None:
        return
    try:
        _client.flush()
    except Exception:
        logger.exception("Error flushing Langfuse on shutdown")


@asynccontextmanager
async def trace_tool(tool_name: str, inputs: dict[str, Any] | None = None) -> AsyncGenerator[None, None]:
    """Async context manager that traces a tool call in Langfuse (no-op if disabled)."""
    client = get_langfuse()
    if client is None:
        yield
        return

    start = time.perf_counter()
    obs = None
    try:
        obs = client.start_observation(name=tool_name, as_type="tool", input=inputs)
        yield
        elapsed = int((time.perf_counter() - start) * 1000)
        if obs is not None:
            obs.update(metadata={"duration_ms": elapsed})
            obs.end()
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        try:
            if obs is not None:
                obs.update(level="ERROR", status_message=str(exc), metadata={"duration_ms": elapsed})
                obs.end()
        except Exception:
            pass
        raise
