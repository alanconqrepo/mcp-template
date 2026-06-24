from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.azure_devops_client import get_ado_client, raise_for_status, resolve_pat_and_org

_API = "api-version=7.1"
_PAT_FIELD = Field(description="PAT Azure DevOps. Utilise AZURE_DEVOPS_DEFAULT_PAT si absent.")


@mcp.tool(
    description=(
        "Pousser un ou plusieurs fichiers sur une branche Azure DevOps en un commit atomique. "
        "Chaque élément de `changes` doit avoir : `path` (chemin absolu du fichier), "
        "`content` (contenu texte, ignoré si change_type=delete), "
        "`change_type` (add | edit | delete, défaut: edit)."
    )
)
async def azure_devops_push_changes(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    branch: Annotated[str, Field(description="Branche cible sur laquelle pousser")],
    message: Annotated[str, Field(description="Message du commit")],
    changes: Annotated[
        list[dict],
        Field(
            description=(
                "Liste de changements. Chaque entrée : "
                "{\"path\": \"/src/foo.py\", \"content\": \"...\", \"change_type\": \"edit\"}"
            )
        ),
    ],
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    if not changes:
        raise RuntimeError("La liste `changes` ne peut pas être vide.")

    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_push_changes", inputs={"project": project, "repo": repo, "branch": branch, "files": len(changes)}):
        async with get_ado_client(effective_pat, org_url) as client:
            # Resolve current commit ID on the target branch
            ref_response = await client.get(
                f"/{project}/_apis/git/repositories/{repo}/refs"
                f"?filter=heads/{branch}&{_API}"
            )
            await raise_for_status(ref_response)
            refs = ref_response.json().get("value", [])
            if not refs:
                raise RuntimeError(f"Branche '{branch}' introuvable dans le dépôt '{repo}'.")
            old_object_id = refs[0]["objectId"]

            # Build the push payload
            commit_changes = []
            for change in changes:
                path = change.get("path", "")
                change_type = change.get("change_type", "edit")
                entry: dict = {
                    "changeType": change_type,
                    "item": {"path": path},
                }
                if change_type != "delete":
                    entry["newContent"] = {
                        "content": change.get("content", ""),
                        "contentType": "rawtext",
                    }
                commit_changes.append(entry)

            payload = {
                "refUpdates": [{"name": f"refs/heads/{branch}", "oldObjectId": old_object_id}],
                "commits": [{"comment": message, "changes": commit_changes}],
            }
            push_response = await client.post(
                f"/{project}/_apis/git/repositories/{repo}/pushes?{_API}",
                json=payload,
            )
            await raise_for_status(push_response)
            push = push_response.json()
            commit = push.get("commits", [{}])[0]
            return {
                "push_id": push.get("pushId"),
                "commit_id": commit.get("commitId"),
                "branch": branch,
                "files_changed": len(changes),
            }
