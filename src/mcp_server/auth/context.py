from __future__ import annotations

from contextvars import ContextVar

# Bearer token of the current MCP caller, set by AuthMiddleware.
# Used by Outlook tools to look up the right per-user token cache.
_current_user_key: ContextVar[str | None] = ContextVar("current_user_key", default=None)
