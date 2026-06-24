from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.deepl_client import get_deepl_translator

_FORMALITY = "default | more | less | prefer_more | prefer_less"


@mcp.tool(
    description=(
        "Translate text using DeepL. Returns the translated text and the detected source language. "
        "Supports optional formality control, a DeepL glossary ID, and a context hint to improve accuracy."
    )
)
async def deepl_translate_text(
    text: Annotated[str, Field(description="The text to translate")],
    target_lang: Annotated[
        str,
        Field(
            description=(
                "Target language code (e.g. 'EN-US', 'FR', 'DE'). "
                "Use deepl_list_target_languages to get valid codes."
            )
        ),
    ],
    source_lang: Annotated[
        str | None,
        Field(description="Source language code (e.g. 'EN', 'FR'). Omit to auto-detect."),
    ] = None,
    formality: Annotated[
        str | None,
        Field(description=f"Formality level for languages that support it: {_FORMALITY}"),
    ] = None,
    glossary_id: Annotated[
        str | None,
        Field(description="DeepL glossary ID to apply during translation"),
    ] = None,
    context: Annotated[
        str | None,
        Field(
            description=(
                "Additional context passed to the DeepL engine to improve accuracy "
                "(this text is not included in the output)"
            )
        ),
    ] = None,
) -> dict:
    async with trace_tool(
        "deepl_translate_text",
        inputs={"target_lang": target_lang, "source_lang": source_lang, "text_length": len(text)},
    ):
        translator = get_deepl_translator()

        kwargs: dict = {}
        if source_lang:
            kwargs["source_lang"] = source_lang
        if formality:
            kwargs["formality"] = formality
        if glossary_id:
            kwargs["glossary"] = glossary_id
        if context:
            kwargs["context"] = context

        result = await asyncio.to_thread(
            translator.translate_text, text, target_lang=target_lang, **kwargs
        )
        return {
            "text": result.text,
            "detected_source_lang": result.detected_source_lang.code,
            "billed_characters": result.billed_characters,
        }
