from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from mcp_server.auth.dependencies import require_auth
from mcp_server.config import get_settings
from mcp_server.observability.langfuse import get_langfuse, shutdown_langfuse

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Enforce authentication on all paths except /health."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        settings = get_settings()
        excluded = {"/health", "/health/"}
        if request.url.path not in excluded:
            try:
                await require_auth(request)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return await call_next(request)


async def _get_tool_names() -> list[str]:
    """Return names of all registered MCP tools."""
    from mcp_server.server import mcp

    tools = await mcp.list_tools()
    return [t.name for t in tools]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Import tools package — triggers auto-discovery and @mcp.tool() registration
    import mcp_server.tools  # noqa: F401

    from mcp_server.server import mcp

    # Create FastMCP ASGI app with the configured mount path as its route
    mcp_asgi = mcp.http_app(path=settings.MCP_MOUNT_PATH, transport="streamable-http")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # FastMCP's session manager must be initialized via its own lifespan.
        # Starlette 1.x does not auto-run mounted sub-app lifespans, so we
        # drive it explicitly from the parent app's lifespan.
        async with mcp_asgi.lifespan(app):
            if settings.AUTH_MODE == "none":
                logger.warning("AUTH_MODE=none — authentication is disabled. Do not use in production.")

            tool_names = await _get_tool_names()
            langfuse_enabled = get_langfuse() is not None

            logger.info(
                "MCP Server '%s' starting\n"
                "  Transport: Streamable HTTP\n"
                "  Mount path: %s\n"
                "  Auth mode: %s\n"
                "  Tools loaded: %s\n"
                "  Langfuse: %s",
                settings.MCP_SERVER_NAME,
                settings.MCP_MOUNT_PATH,
                settings.AUTH_MODE,
                ", ".join(tool_names) if tool_names else "none",
                "enabled" if langfuse_enabled else "disabled",
            )

            yield

            shutdown_langfuse()
            logger.info("MCP Server '%s' shut down", settings.MCP_SERVER_NAME)

    app = FastAPI(title=settings.MCP_SERVER_NAME, lifespan=lifespan)

    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(AuthMiddleware)

    @app.get("/health")
    async def health() -> dict:
        """Public health check endpoint."""
        tool_names = await _get_tool_names()
        return {
            "status": "ok",
            "server_name": settings.MCP_SERVER_NAME,
            "auth_mode": settings.AUTH_MODE,
            "tools_count": len(tool_names),
            "langfuse_enabled": get_langfuse() is not None,
        }

    # Mount FastMCP at root so its internal route (MCP_MOUNT_PATH) is directly
    # accessible. E.g. MCP_MOUNT_PATH=/mcp → endpoint at /mcp.
    app.mount("", mcp_asgi)

    return app


app = create_app()
