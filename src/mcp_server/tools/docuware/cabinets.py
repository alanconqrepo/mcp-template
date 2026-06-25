from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.docuware_client import get_docuware_client


@mcp.tool(
    description=(
        "List all DocuWare file cabinets accessible to the service account. "
        "Returns the cabinet id (GUID), name, and whether it is a basket (tray). "
        "Use the id to search or access documents in a cabinet."
    )
)
async def docuware_list_cabinets() -> dict:
    async with trace_tool("docuware_list_cabinets"):
        client = get_docuware_client()
        cabinets = await client.list_cabinets()
        return {"cabinets": cabinets, "count": len(cabinets)}
