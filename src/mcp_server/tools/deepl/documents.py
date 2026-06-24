from __future__ import annotations

import asyncio
import io
import os
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.azure_blob import download_blob_bytes, generate_blob_sas_url, upload_blob_bytes
from mcp_server.utils.deepl_client import get_deepl_translator

_SUPPORTED_EXTENSIONS = {".docx", ".pdf"}
_FORMALITY = "default | more | less | prefer_more | prefer_less"


def _derive_output_blob_path(input_blob_path: str, output_prefix: str) -> str:
    if output_prefix:
        return f"{output_prefix.rstrip('/')}/{input_blob_path}"
    base, ext = os.path.splitext(input_blob_path)
    return f"{base}_translated{ext}"


def _sync_translate_document(
    translator,
    input_bytes: bytes,
    filename: str,
    target_lang: str,
    source_lang: str | None,
    glossary_id: str | None,
    formality: str | None,
) -> bytes:
    input_io = io.BytesIO(input_bytes)
    output_io = io.BytesIO()
    kwargs: dict = {}
    if source_lang:
        kwargs["source_lang"] = source_lang
    if glossary_id:
        kwargs["glossary"] = glossary_id
    if formality:
        kwargs["formality"] = formality
    translator.translate_document(
        input_io,
        output_io,
        target_lang=target_lang,
        filename=filename,
        **kwargs,
    )
    return output_io.getvalue()


@mcp.tool(
    description=(
        "Translate a Word (.docx) or PDF document stored in Azure Blob Storage using DeepL, "
        "preserving the original formatting and layout. "
        "The translated document is saved back to Azure Blob Storage and a time-limited "
        "SAS download URL is returned. "
        "Note: PDF translation requires a DeepL Pro plan."
    )
)
async def deepl_translate_document(
    input_blob_path: Annotated[
        str,
        Field(
            description=(
                "Path to the source document within the DeepL blob container "
                "(e.g. 'contracts/report.docx')"
            )
        ),
    ],
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
        Field(description="Source language code. Omit for auto-detection."),
    ] = None,
    output_blob_path: Annotated[
        str | None,
        Field(
            description=(
                "Custom output blob path. Defaults to "
                "DEEPL_BLOB_OUTPUT_PREFIX + input_blob_path."
            )
        ),
    ] = None,
    glossary_id: Annotated[
        str | None,
        Field(description="DeepL glossary ID to apply during translation"),
    ] = None,
    formality: Annotated[
        str | None,
        Field(description=f"Formality level for languages that support it: {_FORMALITY}"),
    ] = None,
    sas_expiry_hours: Annotated[
        int,
        Field(description="Hours the SAS download URL remains valid", ge=1, le=168),
    ] = 24,
) -> dict:
    async with trace_tool(
        "deepl_translate_document",
        inputs={
            "input_blob_path": input_blob_path,
            "target_lang": target_lang,
            "source_lang": source_lang,
        },
    ):
        from mcp_server.config import get_settings

        settings = get_settings()

        _, ext = os.path.splitext(input_blob_path)
        if ext.lower() not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. "
                "DeepL document translation supports: "
                + ", ".join(sorted(_SUPPORTED_EXTENSIONS))
            )

        if not settings.DEEPL_BLOB_CONTAINER:
            raise RuntimeError("DEEPL_BLOB_CONTAINER is not configured")

        container = settings.DEEPL_BLOB_CONTAINER
        resolved_output = output_blob_path or _derive_output_blob_path(
            input_blob_path, settings.DEEPL_BLOB_OUTPUT_PREFIX
        )

        if resolved_output == input_blob_path:
            raise ValueError(
                "Output blob path would overwrite the input blob. "
                "Set output_blob_path or configure DEEPL_BLOB_OUTPUT_PREFIX."
            )

        input_bytes = await download_blob_bytes(container, input_blob_path)

        translator = get_deepl_translator()
        filename = os.path.basename(input_blob_path)
        translated_bytes = await asyncio.to_thread(
            _sync_translate_document,
            translator,
            input_bytes,
            filename,
            target_lang,
            source_lang,
            glossary_id,
            formality,
        )

        await upload_blob_bytes(container, resolved_output, translated_bytes)
        sas_url = await generate_blob_sas_url(container, resolved_output, sas_expiry_hours)

        return {
            "input_blob_path": input_blob_path,
            "output_blob_path": resolved_output,
            "target_lang": target_lang,
            "source_lang": source_lang,
            "sas_url": sas_url,
            "sas_expiry_hours": sas_expiry_hours,
            "output_size_bytes": len(translated_bytes),
        }
