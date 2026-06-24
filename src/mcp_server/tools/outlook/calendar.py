from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.msgraph import graph_get, graph_post

_SELECT_EVENTS = (
    "id,subject,start,end,location,organizer,attendees,isAllDay,isCancelled,onlineMeetingUrl"
)


def _format_event(evt: dict) -> dict:
    organizer = evt.get("organizer", {}).get("emailAddress", {})
    attendees = [
        {
            "name": a["emailAddress"].get("name", ""),
            "email": a["emailAddress"]["address"],
            "status": a.get("status", {}).get("response", ""),
        }
        for a in evt.get("attendees", [])
    ]
    return {
        "id": evt["id"],
        "subject": evt.get("subject", ""),
        "start": evt.get("start", {}).get("dateTime", ""),
        "end": evt.get("end", {}).get("dateTime", ""),
        "timezone": evt.get("start", {}).get("timeZone", ""),
        "location": evt.get("location", {}).get("displayName", ""),
        "organizer_name": organizer.get("name", ""),
        "organizer_email": organizer.get("address", ""),
        "attendees": attendees,
        "is_all_day": evt.get("isAllDay", False),
        "is_cancelled": evt.get("isCancelled", False),
        "online_url": evt.get("onlineMeetingUrl") or "",
    }


@mcp.tool(
    description=(
        "Lister les événements du calendrier Outlook dans une plage de dates. "
        "Les récurrences sont développées en instances individuelles. "
        "Retourne titre, heure de début/fin, lieu, organisateur et participants."
    )
)
async def outlook_list_calendar_events(
    start: Annotated[
        str, Field(description="Début de la plage en ISO 8601, ex: '2026-06-24T00:00:00'")
    ],
    end: Annotated[
        str, Field(description="Fin de la plage en ISO 8601, ex: '2026-06-30T23:59:59'")
    ],
    limit: Annotated[
        int, Field(description="Nombre max d'événements à retourner (1–100)", ge=1, le=100)
    ] = 50,
) -> dict:
    async with trace_tool("outlook_list_calendar_events", inputs={"start": start, "end": end}):
        # startDateTime and endDateTime are regular query params for calendarView, not OData $filter
        params = {
            "startDateTime": start,
            "endDateTime": end,
            "$top": limit,
            "$select": _SELECT_EVENTS,
            "$orderby": "start/dateTime",
        }
        data = await graph_get("/me/calendarView", params=params)
        events = [_format_event(e) for e in data.get("value", [])]
        return {"events": events, "count": len(events)}


@mcp.tool(
    description=(
        "Vérifier les disponibilités (libre/occupé) d'une liste de collaborateurs sur une plage horaire. "
        "Utile pour trouver des créneaux de réunion. "
        "Retourne les blocs occupés avec statut (busy, tentative, oof) pour chaque personne."
    )
)
async def outlook_check_free_busy(
    emails: Annotated[
        list[str], Field(description="Adresses email des collaborateurs à vérifier")
    ],
    start: Annotated[
        str, Field(description="Début en ISO 8601, ex: '2026-06-24T09:00:00'")
    ],
    end: Annotated[
        str, Field(description="Fin en ISO 8601, ex: '2026-06-24T18:00:00'")
    ],
    timezone: Annotated[
        str, Field(description="Fuseau horaire IANA, ex: 'Europe/Paris' ou 'UTC'")
    ] = "UTC",
    interval_minutes: Annotated[
        int, Field(description="Granularité des créneaux en minutes (15–60)", ge=15, le=60)
    ] = 30,
) -> dict:
    async with trace_tool("outlook_check_free_busy", inputs={"emails": emails, "start": start, "end": end}):
        body = {
            "schedules": emails,
            "startTime": {"dateTime": start, "timeZone": timezone},
            "endTime": {"dateTime": end, "timeZone": timezone},
            "availabilityViewInterval": interval_minutes,
        }
        data = await graph_post("/me/calendar/getSchedule", body=body)
        schedules = []
        for item in data.get("value", []):
            busy_blocks = [
                {
                    "start": block.get("start", {}).get("dateTime", ""),
                    "end": block.get("end", {}).get("dateTime", ""),
                    "status": block.get("status", ""),
                    "subject": block.get("subject", ""),
                }
                for block in item.get("scheduleItems", [])
                if block.get("status", "free") != "free"
            ]
            schedules.append({
                "email": item.get("scheduleId", ""),
                "availability_view": item.get("availabilityView", ""),
                "busy_blocks": busy_blocks,
            })
        return {"schedules": schedules, "timezone": timezone}
