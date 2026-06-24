from fastapi import HTTPException

from mcp_server.config import get_settings

_INVALID_KEY_RESPONSE = {"detail": "Invalid or missing API key"}


async def validate_api_key(authorization: str | None) -> None:
    """Validate a Bearer API key against the configured API_KEYS list."""
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    key = authorization.removeprefix("Bearer ").strip()
    if key not in settings.API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
