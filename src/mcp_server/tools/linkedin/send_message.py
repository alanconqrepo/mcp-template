from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.config import get_settings
from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.apify import run_apify_actor


@mcp.tool(
    description=(
        "Send a LinkedIn message to a person identified by their profile URL. "
        "Requires LINKEDIN_LI_AT (session cookie) to be configured on the server. "
        "Use sparingly and with personalised messages to comply with LinkedIn's terms of service."
    )
)
async def linkedin_send_message(
    profile_url: Annotated[
        str,
        Field(description="LinkedIn profile URL of the recipient, e.g. https://www.linkedin.com/in/johndoe/"),
    ],
    message: Annotated[
        str,
        Field(description="Message text to send (max ~1900 characters recommended)"),
    ],
) -> dict:
    async with trace_tool(
        "linkedin_send_message",
        inputs={"profile_url": profile_url, "message_length": len(message)},
    ):
        settings = get_settings()
        if not settings.LINKEDIN_LI_AT:
            raise RuntimeError(
                "LINKEDIN_LI_AT is not configured. "
                "Set it to the value of the 'li_at' cookie from an authenticated LinkedIn session."
            )

        results = await run_apify_actor(
            settings.APIFY_ACTOR_SEND_MESSAGE,
            {
                "profileUrls": [profile_url],
                "message": message,
                "cookie": [{"name": "li_at", "value": settings.LINKEDIN_LI_AT}],
            },
        )
        if not results:
            return {"status": "unknown", "profile_url": profile_url}
        item = results[0]
        return {
            "status": item.get("status") or "sent",
            "profile_url": profile_url,
            "detail": item.get("message") or item.get("detail"),
        }
