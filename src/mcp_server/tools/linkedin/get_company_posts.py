from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.config import get_settings
from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.apify import run_apify_actor


@mcp.tool(
    description=(
        "Retrieve recent posts from a LinkedIn company page. Returns post content, publication date, "
        "reactions, comments count, and post type. Useful for competitor activity monitoring."
    )
)
async def linkedin_get_company_posts(
    company_url: Annotated[
        str,
        Field(description="LinkedIn company page URL, e.g. https://www.linkedin.com/company/openai/"),
    ],
    max_posts: Annotated[
        int,
        Field(description="Maximum number of posts to retrieve (default 20, max 100)", ge=1, le=100),
    ] = 20,
) -> dict:
    async with trace_tool(
        "linkedin_get_company_posts",
        inputs={"company_url": company_url, "max_posts": max_posts},
    ):
        settings = get_settings()
        results = await run_apify_actor(
            settings.APIFY_ACTOR_COMPANY_POSTS,
            {"startUrls": [{"url": company_url}], "maxPosts": max_posts},
        )
        posts = [
            {
                "date": item.get("date") or item.get("postedAt"),
                "text": item.get("text") or item.get("content"),
                "likes": item.get("likes") or item.get("reactions"),
                "comments": item.get("comments") or item.get("commentsCount"),
                "shares": item.get("shares") or item.get("reposts"),
                "type": item.get("type") or item.get("postType"),
                "url": item.get("url") or item.get("postUrl"),
            }
            for item in results
        ]
        return {"company_url": company_url, "post_count": len(posts), "posts": posts}
