from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.docuware_client import get_docuware_client


@mcp.tool(
    description=(
        "Search for documents in a DocuWare file cabinet. "
        "Supports index field conditions and/or full-text search — both can be combined (AND). "
        "Use docuware_list_cabinets to get the cabinet_id. "
        "Field names (DBName) are the database names visible in DocuWare administration."
    )
)
async def docuware_search_documents(
    cabinet_id: Annotated[str, Field(description="GUID of the file cabinet to search")],
    conditions: Annotated[
        list[dict] | None,
        Field(
            description=(
                'Index field conditions. Each entry: {"field": "DBNAME", "value": "..."}. '
                'Example: [{"field": "DOCUMENTTYPE", "value": "Invoice"}, {"field": "COMPANY", "value": "Acme"}]'
            )
        ),
    ] = None,
    fulltext: Annotated[
        str | None,
        Field(description="Full-text search term. Combined with field conditions via AND if both provided."),
    ] = None,
    count: Annotated[int, Field(description="Maximum number of results (1–100)", ge=1, le=100)] = 20,
    start: Annotated[int, Field(description="Zero-based offset for pagination", ge=0)] = 0,
) -> dict:
    async with trace_tool(
        "docuware_search_documents",
        inputs={"cabinet_id": cabinet_id, "conditions": conditions, "fulltext": fulltext, "count": count, "start": start},
    ):
        if not conditions and not fulltext:
            return {"error": "Provide at least one of: conditions, fulltext"}
        client = get_docuware_client()
        return await client.search_documents(cabinet_id, conditions, fulltext, count, start)
