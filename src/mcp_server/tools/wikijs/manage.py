from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.wikijs_client import graphql

_DELETE_PAGE_MUTATION = """
mutation($id: Int!) {
  pages {
    delete(id: $id) {
      responseResult { succeeded errorCode slug message }
    }
  }
}
"""


@mcp.tool(description="Permanently delete a Wiki.js page by its numeric ID. This action cannot be undone.")
async def wikijs_delete_page(
    page_id: Annotated[int, Field(description="Numeric ID of the page to delete")],
) -> dict:
    async with trace_tool("wikijs_delete_page", inputs={"page_id": page_id}):
        data = await graphql(_DELETE_PAGE_MUTATION, {"id": page_id})
        response = data.get("pages", {}).get("delete", {}).get("responseResult", {})
        return {
            "succeeded": response.get("succeeded", False),
            "message": response.get("message", ""),
        }
