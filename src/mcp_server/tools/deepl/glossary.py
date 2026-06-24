from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.deepl_client import get_deepl_translator

_GLOSSARY_ID = Field(description="DeepL glossary ID")


@mcp.tool(description="List all DeepL glossaries available for the configured API key.")
async def deepl_list_glossaries() -> dict:
    async with trace_tool("deepl_list_glossaries"):
        translator = get_deepl_translator()
        glossaries = await asyncio.to_thread(translator.list_glossaries)
        return {
            "glossaries": [
                {
                    "glossary_id": g.glossary_id,
                    "name": g.name,
                    "source_lang": g.source_lang,
                    "target_lang": g.target_lang,
                    "entry_count": g.entry_count,
                    "creation_time": g.creation_time.isoformat(),
                    "ready": g.ready,
                }
                for g in glossaries
            ],
            "count": len(glossaries),
        }


@mcp.tool(description="Retrieve all term entries for a specific DeepL glossary.")
async def deepl_get_glossary_entries(
    glossary_id: Annotated[str, _GLOSSARY_ID],
) -> dict:
    async with trace_tool("deepl_get_glossary_entries", inputs={"glossary_id": glossary_id}):
        translator = get_deepl_translator()
        entries = await asyncio.to_thread(translator.get_glossary_entries, glossary_id)
        entry_dict = entries.entries()
        return {
            "glossary_id": glossary_id,
            "entries": entry_dict,
            "count": len(entry_dict),
        }


@mcp.tool(
    description=(
        "Create a new DeepL glossary with custom term pairs. "
        "The entries dict maps source terms to their target-language equivalents."
    )
)
async def deepl_create_glossary(
    name: Annotated[str, Field(description="Human-readable name for the glossary")],
    source_lang: Annotated[str, Field(description="Source language code (e.g. 'EN')")],
    target_lang: Annotated[str, Field(description="Target language code (e.g. 'FR')")],
    entries: Annotated[
        dict[str, str],
        Field(description="Mapping of source terms to their target-language equivalents"),
    ],
) -> dict:
    async with trace_tool(
        "deepl_create_glossary",
        inputs={
            "name": name,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "entry_count": len(entries),
        },
    ):
        translator = get_deepl_translator()
        glossary = await asyncio.to_thread(
            translator.create_glossary,
            name,
            source_lang=source_lang,
            target_lang=target_lang,
            entries=entries,
        )
        return {
            "glossary_id": glossary.glossary_id,
            "name": glossary.name,
            "source_lang": glossary.source_lang,
            "target_lang": glossary.target_lang,
            "entry_count": glossary.entry_count,
            "creation_time": glossary.creation_time.isoformat(),
            "ready": glossary.ready,
        }


@mcp.tool(description="Delete a DeepL glossary by ID. This action is permanent.")
async def deepl_delete_glossary(
    glossary_id: Annotated[str, _GLOSSARY_ID],
) -> dict:
    async with trace_tool("deepl_delete_glossary", inputs={"glossary_id": glossary_id}):
        translator = get_deepl_translator()
        await asyncio.to_thread(translator.delete_glossary, glossary_id)
        return {"deleted": True, "glossary_id": glossary_id}
