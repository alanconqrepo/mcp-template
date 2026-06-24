from fastmcp import FastMCP

from mcp_server.config import get_settings

mcp = FastMCP(get_settings().MCP_SERVER_NAME)
