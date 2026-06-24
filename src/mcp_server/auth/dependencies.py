from fastapi import Request

from mcp_server.auth.api_key import validate_api_key
from mcp_server.auth.oauth2 import validate_oauth2
from mcp_server.config import get_settings


async def require_auth(request: Request) -> None:
    """Route auth validation to the correct backend based on AUTH_MODE."""
    settings = get_settings()
    authorization = request.headers.get("Authorization")

    if settings.AUTH_MODE == "api_key":
        await validate_api_key(authorization)
    elif settings.AUTH_MODE == "oauth2":
        await validate_oauth2(authorization)
    # AUTH_MODE == "none": no-op (warning is emitted once at startup)
