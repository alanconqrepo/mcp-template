from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.msgraph import graph_get, graph_post

_SELECT_LIST = "id,subject,from,receivedDateTime,hasAttachments,isRead,bodyPreview"
_SELECT_FULL = "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,hasAttachments"


def _email_summary(msg: dict) -> dict:
    sender = msg.get("from", {}).get("emailAddress", {})
    return {
        "id": msg["id"],
        "subject": msg.get("subject", ""),
        "from_name": sender.get("name", ""),
        "from_address": sender.get("address", ""),
        "received": msg.get("receivedDateTime", ""),
        "is_read": msg.get("isRead", False),
        "has_attachments": msg.get("hasAttachments", False),
        "preview": msg.get("bodyPreview", ""),
    }


@mcp.tool(
    description=(
        "Lister les emails récents depuis la boîte Outlook de l'utilisateur. "
        "Filtrage optionnel par recherche OData (ex: 'subject:budget', 'from:alice@co.com'). "
        "Retourne expéditeur, sujet, date et aperçu pour chaque email."
    )
)
async def outlook_list_emails(
    limit: Annotated[int, Field(description="Nombre max d'emails à retourner (1–50)", ge=1, le=50)] = 20,
    search: Annotated[
        str | None,
        Field(description="Terme de recherche OData. Ex: 'subject:budget', 'from:alice@co.com'."),
    ] = None,
    folder: Annotated[
        str,
        Field(description="Dossier : 'inbox', 'sentitems', 'drafts', ou ID de dossier."),
    ] = "inbox",
) -> dict:
    async with trace_tool("outlook_list_emails", inputs={"limit": limit, "folder": folder}):
        params: dict = {"$top": limit, "$select": _SELECT_LIST}
        if search:
            params["$search"] = f'"{search}"'
            # $orderby is incompatible with $search in Graph API
        else:
            params["$orderby"] = "receivedDateTime desc"
        data = await graph_get(f"/me/mailFolders/{folder}/messages", params=params)
        emails = [_email_summary(m) for m in data.get("value", [])]
        return {"emails": emails, "count": len(emails)}


@mcp.tool(
    description=(
        "Récupérer le contenu complet d'un email par son ID (obtenu via outlook_list_emails). "
        "Retourne sujet, expéditeur, destinataires, corps en texte brut et présence de pièces jointes."
    )
)
async def outlook_get_email(
    message_id: Annotated[str, Field(description="ID du message Outlook (de outlook_list_emails)")],
) -> dict:
    async with trace_tool("outlook_get_email", inputs={"message_id": message_id}):
        data = await graph_get(
            f"/me/messages/{message_id}",
            params={"$select": _SELECT_FULL},
            extra_headers={"Prefer": 'outlook.body-content-type="text"'},
        )
        sender = data.get("from", {}).get("emailAddress", {})
        to_list = [r["emailAddress"]["address"] for r in data.get("toRecipients", [])]
        cc_list = [r["emailAddress"]["address"] for r in data.get("ccRecipients", [])]
        body = data.get("body", {})
        return {
            "id": data["id"],
            "subject": data.get("subject", ""),
            "from_name": sender.get("name", ""),
            "from_address": sender.get("address", ""),
            "to": to_list,
            "cc": cc_list,
            "received": data.get("receivedDateTime", ""),
            "body_type": body.get("contentType", ""),
            "body": body.get("content", ""),
            "has_attachments": data.get("hasAttachments", False),
        }


@mcp.tool(
    description=(
        "Créer un brouillon de réponse à un email existant. "
        "Le brouillon est sauvegardé dans le dossier Brouillons et NON envoyé. "
        "Retourne l'ID du brouillon pour consultation ou envoi manuel dans Outlook."
    )
)
async def outlook_create_draft_reply(
    message_id: Annotated[str, Field(description="ID du message auquel répondre")],
    body: Annotated[str, Field(description="Texte brut du corps de la réponse")],
    reply_all: Annotated[
        bool, Field(description="Si vrai, répond à tous les destinataires")
    ] = False,
) -> dict:
    async with trace_tool(
        "outlook_create_draft_reply",
        inputs={"message_id": message_id, "reply_all": reply_all},
    ):
        endpoint = "createReplyAll" if reply_all else "createReply"
        data = await graph_post(f"/me/messages/{message_id}/{endpoint}", body={"comment": body})
        to_list = [r["emailAddress"]["address"] for r in data.get("toRecipients", [])]
        return {
            "draft_id": data["id"],
            "subject": data.get("subject", ""),
            "to": to_list,
            "created_at": data.get("createdDateTime", ""),
            "status": "brouillon — non envoyé",
        }
