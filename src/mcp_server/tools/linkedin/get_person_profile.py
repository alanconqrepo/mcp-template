from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.config import get_settings
from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.apify import run_apify_actor


@mcp.tool(
    description=(
        "Retrieve a detailed LinkedIn profile for a person: full name, headline, current position, "
        "work experience, education, skills, and contact info when available. "
        "Use before reaching out to a prospect to personalize your approach."
    )
)
async def linkedin_get_person_profile(
    profile_url: Annotated[
        str,
        Field(
            description="LinkedIn profile URL, e.g. https://www.linkedin.com/in/johndoe/"
        ),
    ],
) -> dict:
    async with trace_tool("linkedin_get_person_profile", inputs={"profile_url": profile_url}):
        settings = get_settings()
        results = await run_apify_actor(
            settings.APIFY_ACTOR_PERSON_PROFILE,
            {"startUrls": [{"url": profile_url}]},
        )
        if not results:
            return {"error": "No data returned for this profile URL"}
        item = results[0]
        return {
            "name": item.get("name") or item.get("fullName"),
            "headline": item.get("headline") or item.get("title"),
            "location": item.get("location") or item.get("addressWithCountry"),
            "about": item.get("about") or item.get("description") or item.get("summary"),
            "current_position": item.get("currentPosition") or item.get("jobTitle"),
            "current_company": item.get("currentCompany") or item.get("company"),
            "experiences": item.get("experiences") or item.get("jobs") or [],
            "education": item.get("educations") or item.get("education") or [],
            "skills": item.get("skills") or [],
            "linkedin_url": item.get("linkedinUrl") or item.get("url") or profile_url,
        }
