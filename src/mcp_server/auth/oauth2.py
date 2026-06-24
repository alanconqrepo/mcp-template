from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import jwt
from fastapi import HTTPException

from mcp_server.config import get_settings

logger = logging.getLogger(__name__)

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from the configured URL, using a 1-hour in-memory cache."""
    global _jwks_cache, _jwks_fetched_at

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.OAUTH2_JWKS_URL)  # type: ignore[arg-type]
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_fetched_at = now
        return _jwks_cache


async def validate_oauth2(authorization: str | None) -> None:
    """Validate a Bearer JWT token against the configured JWKS endpoint."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    token = authorization.removeprefix("Bearer ").strip()
    settings = get_settings()

    try:
        jwks = await _fetch_jwks()
        signing_key = jwt.PyJWKClient(settings.OAUTH2_JWKS_URL).get_signing_key_from_jwt(token)  # type: ignore[arg-type]
        jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.OAUTH2_AUDIENCE,
            issuer=settings.OAUTH2_ISSUER,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as exc:
        logger.error("OAuth2 validation error: %s", exc)
        raise HTTPException(status_code=401, detail="Authentication failed")
