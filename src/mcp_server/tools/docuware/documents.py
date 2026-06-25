from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.azure_blob import download_blob_bytes, generate_blob_sas_url, upload_blob_bytes
from mcp_server.utils.docuware_client import get_docuware_client

_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "image/tiff": ".tiff",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def _ext_from_content_type(content_type: str) -> str:
    return _MIME_TO_EXT.get(content_type.split(";")[0].strip(), "")


@mcp.tool(
    description=(
        "Get the metadata and all index field values for a DocuWare document. "
        "Returns field values, content type, page count, and timestamps."
    )
)
async def docuware_get_document_info(
    cabinet_id: Annotated[str, Field(description="GUID of the file cabinet")],
    doc_id: Annotated[int, Field(description="Numeric DocuWare document ID", gt=0)],
) -> dict:
    async with trace_tool(
        "docuware_get_document_info",
        inputs={"cabinet_id": cabinet_id, "doc_id": doc_id},
    ):
        client = get_docuware_client()
        return await client.get_document(cabinet_id, doc_id)


@mcp.tool(
    description=(
        "Download a DocuWare document and store it in Azure Blob Storage. "
        "Returns a 24-hour SAS URL for direct access, the blob path, and file metadata. "
        "The blob path is auto-generated as '{DOCUWARE_BLOB_PREFIX}{cabinet_id}/{doc_id}.ext' if not specified."
    )
)
async def docuware_download_to_blob(
    cabinet_id: Annotated[str, Field(description="GUID of the file cabinet")],
    doc_id: Annotated[int, Field(description="Numeric DocuWare document ID", gt=0)],
    blob_path: Annotated[
        str | None,
        Field(description="Destination blob path. Auto-generated from cabinet_id and doc_id if omitted."),
    ] = None,
) -> dict:
    async with trace_tool(
        "docuware_download_to_blob",
        inputs={"cabinet_id": cabinet_id, "doc_id": doc_id, "blob_path": blob_path},
    ):
        from mcp_server.config import get_settings

        settings = get_settings()
        container = settings.AZURE_BLOB_CONTAINER_NAME
        if not container:
            return {"error": "AZURE_BLOB_CONTAINER_NAME is not configured"}

        client = get_docuware_client()
        file_bytes, content_type = await client.download_file(cabinet_id, doc_id)

        ext = _ext_from_content_type(content_type)
        resolved_path = blob_path or f"{settings.DOCUWARE_BLOB_PREFIX}{cabinet_id}/{doc_id}{ext}"

        await upload_blob_bytes(container, resolved_path, file_bytes)
        sas_url = await generate_blob_sas_url(container, resolved_path, expiry_hours=24)

        return {
            "blob_path": resolved_path,
            "container": container,
            "content_type": content_type,
            "size_bytes": len(file_bytes),
            "sas_url": sas_url,
        }


@mcp.tool(
    description=(
        "Upload a document from Azure Blob Storage to a DocuWare file cabinet. "
        "Reads the file from blob storage and indexes it with the provided field values. "
        "Returns the new DocuWare document ID."
    )
)
async def docuware_upload_document(
    cabinet_id: Annotated[str, Field(description="GUID of the target file cabinet")],
    blob_path: Annotated[
        str, Field(description="Source file path in Azure Blob Storage (e.g. 'incoming/invoice.pdf')")
    ],
    filename: Annotated[
        str, Field(description="Filename to register in DocuWare (e.g. 'invoice_2024.pdf')")
    ],
    index_fields: Annotated[
        dict,
        Field(
            description=(
                'Index field values keyed by DocuWare database field name. '
                'Example: {"DOCUMENTTYPE": "Invoice", "COMPANY": "Acme Corp", "INVOICEDATE": "2024-01-15"}'
            )
        ),
    ],
) -> dict:
    async with trace_tool(
        "docuware_upload_document",
        inputs={"cabinet_id": cabinet_id, "blob_path": blob_path, "filename": filename},
    ):
        from mcp_server.config import get_settings

        settings = get_settings()
        container = settings.AZURE_BLOB_CONTAINER_NAME
        if not container:
            return {"error": "AZURE_BLOB_CONTAINER_NAME is not configured"}

        file_bytes = await download_blob_bytes(container, blob_path)
        client = get_docuware_client()
        doc_id = await client.upload_document(cabinet_id, file_bytes, filename, index_fields)
        return {"doc_id": doc_id, "cabinet_id": cabinet_id, "filename": filename}
