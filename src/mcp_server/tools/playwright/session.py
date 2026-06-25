from __future__ import annotations

import asyncio

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from mcp_server.auth.context import _current_user_key

_lock = asyncio.Lock()
_playwright: Playwright | None = None
_browser: Browser | None = None
# Per-user sessions keyed by the bearer token / API key set in AuthMiddleware
_sessions: dict[str, tuple[BrowserContext, Page]] = {}


async def _ensure_browser() -> Browser:
    global _playwright, _browser
    async with _lock:
        if _browser is None or not _browser.is_connected():
            if _playwright is not None:
                try:
                    await _playwright.stop()
                except Exception:
                    pass
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(headless=True)
    return _browser


async def get_page() -> Page:
    """Return the active Page for the current user, creating a new session if needed."""
    user_key = _current_user_key.get() or "__anonymous__"

    existing = _sessions.get(user_key)
    if existing is not None:
        ctx, page = existing
        if not page.is_closed():
            return page
        _sessions.pop(user_key, None)
        try:
            await ctx.close()
        except Exception:
            pass

    browser = await _ensure_browser()
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = await ctx.new_page()
    _sessions[user_key] = (ctx, page)
    return page


async def close_session() -> None:
    """Close and discard the current user's browser session."""
    user_key = _current_user_key.get() or "__anonymous__"
    entry = _sessions.pop(user_key, None)
    if entry is None:
        return
    ctx, page = entry
    try:
        await page.close()
    except Exception:
        pass
    try:
        await ctx.close()
    except Exception:
        pass
