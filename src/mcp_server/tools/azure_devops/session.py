from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.azure_devops_client import store_session_pat


@mcp.tool(
    description=(
        "Configurer le PAT Azure DevOps pour cette session. "
        "À appeler une seule fois en début de conversation — les autres tools azure_devops "
        "utiliseront automatiquement ce PAT sans qu'il soit nécessaire de le répéter."
    )
)
async def azure_devops_configure(
    pat: Annotated[str, Field(description="Personal Access Token Azure DevOps")],
    ctx: Context,
) -> dict:
    async with trace_tool("azure_devops_configure", inputs={}):
        store_session_pat(ctx.session, pat)
        return {"configured": True, "message": "PAT Azure DevOps enregistré pour cette session."}
