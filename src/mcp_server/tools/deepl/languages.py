from __future__ import annotations

import asyncio

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.deepl_client import get_deepl_translator


@mcp.tool(description="List all source languages supported by DeepL for translation input.")
async def deepl_list_source_languages() -> dict:
    async with trace_tool("deepl_list_source_languages"):
        translator = get_deepl_translator()
        langs = await asyncio.to_thread(translator.get_source_languages)
        return {
            "languages": [{"code": lang.code, "name": lang.name} for lang in langs],
            "count": len(langs),
        }


@mcp.tool(
    description=(
        "List all target languages supported by DeepL for translation output, "
        "including whether formality control is available for each language."
    )
)
async def deepl_list_target_languages() -> dict:
    async with trace_tool("deepl_list_target_languages"):
        translator = get_deepl_translator()
        langs = await asyncio.to_thread(translator.get_target_languages)
        return {
            "languages": [
                {
                    "code": lang.code,
                    "name": lang.name,
                    "supports_formality": lang.supports_formality,
                }
                for lang in langs
            ],
            "count": len(langs),
        }
