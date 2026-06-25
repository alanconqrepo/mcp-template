from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from mcp_server.auth.context import _current_user_key
from mcp_server.auth.dependencies import require_auth
from mcp_server.config import get_settings
from mcp_server.observability.langfuse import get_langfuse, shutdown_langfuse

logger = logging.getLogger(__name__)

# Temporary storage for in-progress PKCE flows: state → {flow, api_key, created_at}
# Entries expire after 10 minutes. Module-level dict is fine for single-process deployments.
_pending_flows: dict[str, dict] = {}

_OAUTH_EXCLUDED = {"/auth/outlook", "/auth/outlook/", "/auth/outlook/callback", "/auth/outlook/callback/"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Enforce authentication on all paths except /health and /auth/outlook*."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        settings = get_settings()
        excluded = {"/health", "/health/"} | _OAUTH_EXCLUDED
        if request.url.path not in excluded:
            try:
                await require_auth(request)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        # Propagate the caller's bearer token as a stable per-user identifier
        # so Outlook tools can look up the right MSAL token cache.
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            key = authorization.removeprefix("Bearer ").strip()
            ctx_token = _current_user_key.set(key)
            try:
                return await call_next(request)
            finally:
                _current_user_key.reset(ctx_token)

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
            from mcp_server.utils.pgvector_pool import close_pool
            await close_pool()
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

    @app.get("/auth/outlook", response_class=RedirectResponse)
    async def outlook_auth_start(api_key: str) -> RedirectResponse:
        """
        Start the Microsoft OAuth2 PKCE flow for an Outlook connection.

        The user visits this URL once in their browser, passing their MCP API key.
        They are redirected to Microsoft login, then back to /auth/outlook/callback.
        After that, their Outlook tools work transparently with no extra parameters.
        """
        import msal  # lazy import — only needed if Outlook is configured

        from mcp_server.utils.msgraph import OUTLOOK_SCOPES

        cfg = get_settings()
        if not cfg.AZURE_TENANT_ID or not cfg.AZURE_CLIENT_ID:
            raise HTTPException(
                status_code=503,
                detail="Azure non configuré. Définissez AZURE_TENANT_ID et AZURE_CLIENT_ID dans .env.",
            )

        # Validate api_key in api_key auth mode; accept opaque identifier otherwise.
        if cfg.AUTH_MODE == "api_key" and api_key not in cfg.API_KEYS:
            raise HTTPException(status_code=401, detail="Clé API invalide.")

        msal_app = msal.PublicClientApplication(
            client_id=cfg.AZURE_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{cfg.AZURE_TENANT_ID}",
        )
        flow = msal_app.initiate_auth_code_flow(
            scopes=OUTLOOK_SCOPES,
            redirect_uri=cfg.OUTLOOK_REDIRECT_URI,
        )

        # Clean up expired pending flows before adding a new one
        now = time.time()
        expired = [s for s, v in _pending_flows.items() if now - v["created_at"] > 600]
        for s in expired:
            del _pending_flows[s]

        _pending_flows[flow["state"]] = {"flow": flow, "api_key": api_key, "created_at": now}
        return RedirectResponse(flow["auth_uri"])

    @app.get("/auth/outlook/callback", response_class=HTMLResponse)
    async def outlook_auth_callback(request: Request) -> HTMLResponse:
        """Handle Microsoft's OAuth2 redirect and persist the user's token cache."""
        import msal

        params = dict(request.query_params)
        state = params.get("state", "")

        if not state or state not in _pending_flows:
            return HTMLResponse(
                _html_page("Erreur", "Session expirée ou state invalide. "
                           "Recommencez depuis <code>/auth/outlook?api_key=VOTRE_CLE</code>."),
                status_code=400,
            )

        pending = _pending_flows.pop(state)
        if time.time() - pending["created_at"] > 600:
            return HTMLResponse(
                _html_page("Session expirée", "La fenêtre de 10 minutes est dépassée. "
                           "Recommencez depuis <code>/auth/outlook?api_key=VOTRE_CLE</code>."),
                status_code=400,
            )

        if "error" in params:
            desc = params.get("error_description", params["error"])
            return HTMLResponse(_html_page("Erreur Microsoft", desc), status_code=400)

        cfg = get_settings()
        cache = msal.SerializableTokenCache()
        msal_app = msal.PublicClientApplication(
            client_id=cfg.AZURE_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{cfg.AZURE_TENANT_ID}",
            token_cache=cache,
        )

        result = msal_app.acquire_token_by_auth_code_flow(
            auth_code_flow=pending["flow"],
            auth_response=params,
        )

        if "error" in result:
            desc = result.get("error_description", result["error"])
            return HTMLResponse(_html_page("Erreur d'authentification", desc), status_code=400)

        tokens_dir = Path(cfg.OUTLOOK_TOKENS_DIR)
        tokens_dir.mkdir(parents=True, exist_ok=True)
        user_hash = sha256(pending["api_key"].encode()).hexdigest()
        (tokens_dir / f"{user_hash}.json").write_text(cache.serialize())

        account = result.get("id_token_claims", {}).get("preferred_username", "votre compte")
        return HTMLResponse(
            _html_page(
                "✓ Outlook connecté",
                f"Connecté en tant que <strong>{account}</strong>.<br><br>"
                "Vous pouvez fermer cette fenêtre et utiliser les outils Outlook via OpenWebUI.",
            )
        )

    # Mount FastMCP at root so its internal route (MCP_MOUNT_PATH) is directly
    # accessible. E.g. MCP_MOUNT_PATH=/mcp → endpoint at /mcp.
    app.mount("", mcp_asgi)

    return app


def _html_page(title: str, body: str) -> str:
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        f"<style>body{{font-family:sans-serif;max-width:600px;margin:60px auto;padding:0 20px}}"
        f"h1{{color:#1a1a1a}}</style></head>"
        f"<body><h1>{title}</h1><p>{body}</p></body></html>"
    )


app = create_app()
