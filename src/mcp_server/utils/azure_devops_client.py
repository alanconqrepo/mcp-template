from __future__ import annotations

import base64
import weakref

import httpx

# Per-session PAT storage — keyed on ctx.session (ServerSession object).
# WeakKeyDictionary ensures entries are GC'd automatically when the session ends.
_session_pats: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def store_session_pat(session: object, pat: str) -> None:
    _session_pats[session] = pat


def get_ado_client(pat: str, org_url: str) -> httpx.AsyncClient:
    """Return a configured AsyncClient for Azure DevOps REST API."""
    token = base64.b64encode(f":{pat}".encode()).decode()
    return httpx.AsyncClient(
        base_url=org_url,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def raise_for_status(response: httpx.Response) -> None:
    """Raise a descriptive RuntimeError on HTTP error responses."""
    if response.is_error:
        try:
            body = response.text
        except Exception:
            body = "<unreadable>"
        raise RuntimeError(f"Azure DevOps API error {response.status_code}: {body}")


def resolve_pat_and_org(pat: str | None, session: object | None = None) -> tuple[str, str]:
    """Return (effective_pat, org_url).

    Resolution order: explicit pat → session storage → AZURE_DEVOPS_DEFAULT_PAT → error.
    """
    from mcp_server.config import get_settings

    settings = get_settings()
    effective_pat = (
        pat
        or (session is not None and _session_pats.get(session))
        or settings.AZURE_DEVOPS_DEFAULT_PAT
    )
    if not effective_pat:
        raise RuntimeError(
            "PAT non configuré. Appelle d'abord `azure_devops_configure(pat='...')` "
            "ou fournis le paramètre `pat`, ou configure AZURE_DEVOPS_DEFAULT_PAT."
        )
    return effective_pat, settings.AZURE_DEVOPS_ORG_URL
