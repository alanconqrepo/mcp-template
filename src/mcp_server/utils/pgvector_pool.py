from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_pool = None


async def get_pool():
    """Return the shared AsyncConnectionPool, initialising it on first call."""
    global _pool
    if _pool is not None:
        return _pool

    from psycopg_pool import AsyncConnectionPool
    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.PGVECTOR_DSN:
        raise RuntimeError(
            "PGVECTOR_DSN is not configured. "
            "Set it to a PostgreSQL DSN, e.g. postgresql://user:pass@host:5432/db"
        )

    _pool = AsyncConnectionPool(
        settings.PGVECTOR_DSN,
        min_size=settings.PGVECTOR_POOL_MIN_SIZE,
        max_size=settings.PGVECTOR_POOL_MAX_SIZE,
        open=False,
        configure=_configure_connection,
    )
    await _pool.open()
    logger.info("pgvector connection pool opened (min=%d max=%d)", settings.PGVECTOR_POOL_MIN_SIZE, settings.PGVECTOR_POOL_MAX_SIZE)
    return _pool


async def _configure_connection(conn) -> None:
    """Register the pgvector codec on every new connection."""
    from pgvector.psycopg import register_vector_async
    await register_vector_async(conn)


async def close_pool() -> None:
    """Drain and close the pool — called at application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("pgvector connection pool closed")
