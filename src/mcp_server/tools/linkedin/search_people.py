from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.config import get_settings
from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.apify import run_apify_actor


@mcp.tool(
    description=(
        "Search LinkedIn for people matching given criteria. Returns name, current title, "
        "company, location, and LinkedIn profile URL. Use for prospecting and identifying "
        "decision-makers or contacts."
    )
)
async def linkedin_search_people(
    keywords: Annotated[
        str | None,
        Field(description="Keywords to search for (name, skill, technology, etc.)"),
    ] = None,
    title: Annotated[
        str | None,
        Field(description="Job title filter, e.g. 'CTO', 'Head of Sales', 'VP Engineering'"),
    ] = None,
    company: Annotated[
        str | None,
        Field(description="Current or past company name filter"),
    ] = None,
    location: Annotated[
        str | None,
        Field(description="Location filter, e.g. 'Paris', 'France', 'San Francisco Bay Area'"),
    ] = None,
    max_results: Annotated[
        int,
        Field(description="Maximum number of profiles to return (default 20, max 50)", ge=1, le=50),
    ] = 20,
) -> dict:
    async with trace_tool(
        "linkedin_search_people",
        inputs={"keywords": keywords, "title": title, "company": company, "location": location},
    ):
        settings = get_settings()
        actor_input: dict = {"maxResults": max_results}
        if keywords:
            actor_input["keywords"] = keywords
        if title:
            actor_input["title"] = title
        if company:
            actor_input["company"] = company
        if location:
            actor_input["location"] = location

        results = await run_apify_actor(settings.APIFY_ACTOR_SEARCH_PEOPLE, actor_input)
        people = [
            {
                "name": item.get("name") or item.get("fullName"),
                "title": item.get("title") or item.get("headline") or item.get("jobTitle"),
                "company": item.get("company") or item.get("currentCompany"),
                "location": item.get("location"),
                "linkedin_url": item.get("linkedinUrl") or item.get("profileUrl") or item.get("url"),
            }
            for item in results
        ]
        return {"result_count": len(people), "people": people}
