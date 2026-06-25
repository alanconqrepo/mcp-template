from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.config import get_settings
from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.apify import run_apify_actor


@mcp.tool(
    description=(
        "Search LinkedIn for companies matching given criteria. Returns company name, industry, "
        "size, location, and LinkedIn URL. Useful for building prospect lists or market mapping."
    )
)
async def linkedin_search_companies(
    keywords: Annotated[
        str | None,
        Field(description="Keywords to search for (company name, product, technology, etc.)"),
    ] = None,
    industry: Annotated[
        str | None,
        Field(description="Industry filter, e.g. 'Software Development', 'Financial Services'"),
    ] = None,
    location: Annotated[
        str | None,
        Field(description="Location filter, e.g. 'Paris', 'France', 'Greater Paris Area'"),
    ] = None,
    company_size: Annotated[
        str | None,
        Field(
            description=(
                "Employee count range filter. "
                "Values: '1-10', '11-50', '51-200', '201-500', '501-1000', '1001-5000', '5001-10000', '10001+'"
            )
        ),
    ] = None,
    max_results: Annotated[
        int,
        Field(description="Maximum number of companies to return (default 20, max 50)", ge=1, le=50),
    ] = 20,
) -> dict:
    async with trace_tool(
        "linkedin_search_companies",
        inputs={"keywords": keywords, "industry": industry, "location": location},
    ):
        settings = get_settings()
        actor_input: dict = {"maxResults": max_results, "searchType": "companies"}
        if keywords:
            actor_input["keywords"] = keywords
        if industry:
            actor_input["industry"] = industry
        if location:
            actor_input["location"] = location
        if company_size:
            actor_input["companySize"] = company_size

        results = await run_apify_actor(settings.APIFY_ACTOR_SEARCH_COMPANIES, actor_input)
        companies = [
            {
                "name": item.get("name") or item.get("companyName"),
                "linkedin_url": item.get("linkedinUrl") or item.get("url"),
                "industry": item.get("industry"),
                "company_size": item.get("companySize") or item.get("employeeCount"),
                "location": item.get("location") or item.get("headquarters"),
                "website": item.get("website"),
            }
            for item in results
        ]
        return {"result_count": len(companies), "companies": companies}
