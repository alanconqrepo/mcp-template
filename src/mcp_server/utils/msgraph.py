from __future__ import annotations

import asyncio
import logging
from hashlib import sha256
from pathlib import Path

import httpx
import msal

from mcp_server.auth.context import _current_user_key

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

OUTLOOK_SCOPES = [
    "Mail.Read",
    "Mail.ReadWrite",
    "Calendars.Read",
    "Calendars.Read.Shared",
    "User.Read",
    "User.ReadBasic.All",
]

# Prevents concurrent MSAL token refreshes for the same user from racing.
_token_lock = asyncio.Lock()


def _get_settings():
    from mcp_server.config import get_settings

    cfg = get_settings()
    if not cfg.AZURE_TENANT_ID or not cfg.AZURE_CLIENT_ID:
        raise RuntimeError(
            "Configuration Azure manquante. Définissez AZURE_TENANT_ID et AZURE_CLIENT_ID dans .env."
        )
    return cfg


async def get_user_token() -> str:
    """Load the current user's MSAL cache and return a valid access token.

    Refreshes automatically when the cached token is expired.
    Raises RuntimeError if the user hasn't authenticated via /auth/outlook.
    """
    api_key = _current_user_key.get()
    if not api_key:
        raise RuntimeError("Aucun utilisateur authentifié pour cet appel MCP.")

    cfg = _get_settings()
    tokens_dir = Path(cfg.OUTLOOK_TOKENS_DIR)
    cache_path = tokens_dir / f"{sha256(api_key.encode()).hexdigest()}.json"

    if not cache_path.exists():
        auth_url = cfg.OUTLOOK_REDIRECT_URI.rsplit("/callback", 1)[0]
        raise RuntimeError(
            f"Compte Outlook non connecté. Visitez {auth_url}?api_key=VOTRE_CLE "
            "dans votre navigateur pour vous connecter."
        )

    async with _token_lock:
        cache = msal.SerializableTokenCache()
        cache.deserialize(cache_path.read_text())

        msal_app = msal.PublicClientApplication(
            client_id=cfg.AZURE_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{cfg.AZURE_TENANT_ID}",
            token_cache=cache,
        )

        accounts = msal_app.get_accounts()
        if not accounts:
            cache_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Session Outlook expirée. Visitez /auth/outlook?api_key=VOTRE_CLE pour vous reconnecter."
            )

        # acquire_token_silent uses MSAL's requests-based HTTP client — run in thread
        # to avoid blocking the asyncio event loop.
        result = await asyncio.to_thread(
            msal_app.acquire_token_silent, OUTLOOK_SCOPES, account=accounts[0]
        )

        if not result or "access_token" not in result:
            cache_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Impossible de renouveler le token Outlook. "
                "Visitez /auth/outlook?api_key=VOTRE_CLE pour vous reconnecter."
            )

        if cache.has_state_changed:
            cache_path.write_text(cache.serialize())
            logger.debug("Token Outlook rafraîchi pour l'utilisateur (hash: %s…)", cache_path.stem[:8])

    return result["access_token"]


def _raise_for_graph_error(response: httpx.Response) -> None:
    if response.is_error:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(f"Microsoft Graph {response.status_code}: {detail}")


async def graph_get(
    path: str,
    params: dict | None = None,
    extra_headers: dict | None = None,
) -> dict:
    """GET from Microsoft Graph v1.0 and return parsed JSON."""
    token = await get_user_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    async with httpx.AsyncClient(base_url=_GRAPH_BASE, headers=headers, timeout=30.0) as client:
        response = await client.get(path, params=params)
    _raise_for_graph_error(response)
    return response.json()


async def graph_post(path: str, body: dict) -> dict:
    """POST to Microsoft Graph v1.0 and return parsed JSON."""
    token = await get_user_token()
    async with httpx.AsyncClient(
        base_url=_GRAPH_BASE,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    ) as client:
        response = await client.post(path, json=body)
    _raise_for_graph_error(response)
    return response.json()
