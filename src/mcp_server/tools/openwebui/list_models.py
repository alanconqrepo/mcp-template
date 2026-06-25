from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.openwebui_client import get_openwebui_client, raise_for_status


@mcp.tool(
    description=(
        "List all models available in the OpenWebUI instance. "
        "Use this before calling a model to discover valid model IDs."
    )
)
async def list_openwebui_models() -> dict:
    async with trace_tool("list_openwebui_models"):
        try:
            async with get_openwebui_client() as client:
                response = await client.get("/api/models")
                await raise_for_status(response)
                data = response.json()
            models = [
                {"id": m["id"], "name": m.get("name", m["id"])}
                for m in data.get("data", [])
            ]
            return {"models": models, "count": len(models)}
        except RuntimeError as e:
            return {"error": str(e)}
