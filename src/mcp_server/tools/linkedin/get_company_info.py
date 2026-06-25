from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.config import get_settings
from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.apify import run_apify_actor


@mcp.tool(
    description=(
        "Retrieve a LinkedIn company profile: name, industry, employee count, description, "
        "headquarters, website, and LinkedIn URL. Use this for competitor research or to enrich "
        "a prospect's company data."
    )
)
async def linkedin_get_company_info(
    company_url: Annotated[
        str,
        Field(description="LinkedIn company page URL, e.g. https://www.linkedin.com/company/openai/"),
    ],
) -> dict:
    async with trace_tool("linkedin_get_company_info", inputs={"company_url": company_url}):
        settings = get_settings()
        results = await run_apify_actor(
            settings.APIFY_ACTOR_COMPANY_INFO,
            {"startUrls": [{"url": company_url}]},
        )
        if not results:
            return {"error": "No data returned for this company URL"}
        item = results[0]
        return {
            "name": item.get("name"),
            "linkedin_url": item.get("linkedinUrl") or company_url,
            "website": item.get("website"),
            "industry": item.get("industry"),
            "company_size": item.get("companySize") or item.get("employeeCount"),
            "headquarters": item.get("headquarters") or item.get("location"),
            "description": item.get("description"),
            "founded": item.get("founded"),
            "specialties": item.get("specialties"),
        }
