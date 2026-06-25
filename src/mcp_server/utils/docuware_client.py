from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)

_PLATFORM_PATH = "/DocuWare/Platform"


class DocuWareClient:
    def __init__(self, base_url: str, username: str, password: str, organization: str) -> None:
        self._base = base_url.rstrip("/") + _PLATFORM_PATH
        self._username = username
        self._password = password
        self._organization = organization
        self._client = httpx.AsyncClient(
            headers={"Accept": "application/json"},
            timeout=60.0,
            follow_redirects=True,
        )
        self._lock = asyncio.Lock()
        self._logged_in = False

    async def _logon(self) -> None:
        resp = await self._client.post(
            f"{self._base}/Account/Logon",
            json={
                "LicenseType": "PlatformService",
                "Username": self._username,
                "Password": self._password,
                "Organization": self._organization,
                "RedirectToMyselfInCaseOfError": False,
                "RememberMe": True,
            },
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if resp.is_error:
            raise RuntimeError(f"DocuWare logon failed ({resp.status_code}): {resp.text[:200]}")
        self._logged_in = True
        logger.info("DocuWare session established")

    async def _ensure_session(self) -> None:
        if not self._logged_in:
            async with self._lock:
                if not self._logged_in:
                    await self._logon()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        await self._ensure_session()
        resp = await self._client.request(method, f"{self._base}{path}", **kwargs)
        if resp.status_code == 401:
            # Session expired — re-authenticate once and retry
            async with self._lock:
                self._logged_in = False
                await self._logon()
            resp = await self._client.request(method, f"{self._base}{path}", **kwargs)
        return resp

    def _raise_for_error(self, resp: httpx.Response, context: str) -> None:
        if resp.is_error:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:200]
            raise RuntimeError(f"DocuWare {context} ({resp.status_code}): {detail}")

    async def list_cabinets(self) -> list[dict]:
        resp = await self._request("GET", "/FileCabinets")
        self._raise_for_error(resp, "list_cabinets")
        return [
            {"id": c["Id"], "name": c["Name"], "is_basket": c.get("IsBasket", False)}
            for c in resp.json().get("FileCabinet", [])
        ]

    async def search_documents(
        self,
        cabinet_id: str,
        conditions: list[dict] | None,
        fulltext: str | None,
        count: int,
        start: int,
    ) -> dict:
        expr_conditions: list[dict] = []
        if conditions:
            expr_conditions.extend(
                {"DBName": c["field"], "Value": [c["value"]]} for c in conditions
            )
        if fulltext:
            expr_conditions.append({"DBName": "FULLTEXT", "Value": [fulltext]})

        resp = await self._request(
            "POST",
            f"/FileCabinets/{cabinet_id}/Query/DialogExpression",
            json={"Condition": expr_conditions, "Operation": "And", "Count": count, "Start": start},
        )
        self._raise_for_error(resp, "search_documents")
        data = resp.json()
        items = data.get("Items", [])
        return {
            "total": data.get("Count", len(items)),
            "start": start,
            "items": [
                {
                    "id": item.get("Id"),
                    "fields": {f["FieldName"]: f.get("Item") for f in item.get("Fields", [])},
                    "content_type": item.get("ContentType"),
                    "created": item.get("CreatedAt"),
                    "modified": item.get("LastModified"),
                }
                for item in items
            ],
        }

    async def get_document(self, cabinet_id: str, doc_id: int) -> dict:
        resp = await self._request(
            "GET",
            f"/FileCabinets/{cabinet_id}/Documents/{doc_id}",
            params={"Fields": "All"},
        )
        self._raise_for_error(resp, "get_document")
        data = resp.json()
        return {
            "id": data.get("Id"),
            "cabinet_id": cabinet_id,
            "content_type": data.get("ContentType"),
            "created": data.get("CreatedAt"),
            "modified": data.get("LastModified"),
            "page_count": data.get("PageCount"),
            "fields": {f["FieldName"]: f.get("Item") for f in data.get("Fields", [])},
        }

    async def download_file(self, cabinet_id: str, doc_id: int) -> tuple[bytes, str]:
        """Download the document file. Returns (content_bytes, content_type)."""
        resp = await self._request(
            "GET",
            f"/FileCabinets/{cabinet_id}/Documents/{doc_id}/FileDownload",
            params={"targetFileType": "Auto", "keepAnnotations": "False"},
        )
        self._raise_for_error(resp, "download_file")
        return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

    async def upload_document(
        self,
        cabinet_id: str,
        file_bytes: bytes,
        filename: str,
        index_fields: dict[str, str],
    ) -> int | None:
        """Upload a document to the cabinet with index fields. Returns the new document ID."""
        fields_json = json.dumps({
            "Fields": [
                {"FieldName": k, "ItemElementName": "String", "Item": v}
                for k, v in index_fields.items()
            ]
        })
        mime_type, _ = mimetypes.guess_type(filename)
        resp = await self._request(
            "POST",
            f"/FileCabinets/{cabinet_id}/Documents",
            files=[
                ("document", (None, fields_json, "application/json")),
                ("file[]", (filename, file_bytes, mime_type or "application/octet-stream")),
            ],
        )
        self._raise_for_error(resp, "upload_document")
        return resp.json().get("Id")


@lru_cache(maxsize=1)
def get_docuware_client() -> DocuWareClient:
    from mcp_server.config import get_settings

    cfg = get_settings()
    if not cfg.DOCUWARE_URL:
        raise RuntimeError("DOCUWARE_URL is not configured")
    return DocuWareClient(
        base_url=cfg.DOCUWARE_URL,
        username=cfg.DOCUWARE_USERNAME,
        password=cfg.DOCUWARE_PASSWORD,
        organization=cfg.DOCUWARE_ORGANIZATION,
    )
