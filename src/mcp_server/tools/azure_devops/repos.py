from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.azure_devops_client import get_ado_client, raise_for_status, resolve_pat_and_org

_API = "api-version=7.1"
_PAT_FIELD = Field(description="PAT Azure DevOps. Utilise AZURE_DEVOPS_DEFAULT_PAT si absent.")


@mcp.tool(description="Lister tous les dépôts Git d'un projet Azure DevOps.")
async def azure_devops_list_repos(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_list_repos", inputs={"project": project}):
        async with get_ado_client(effective_pat, org_url) as client:
            response = await client.get(f"/{project}/_apis/git/repositories?{_API}")
            await raise_for_status(response)
            data = response.json()
            return {
                "count": data.get("count", 0),
                "repos": [
                    {"id": r["id"], "name": r["name"], "default_branch": r.get("defaultBranch", ""), "remote_url": r.get("remoteUrl", "")}
                    for r in data.get("value", [])
                ],
            }


@mcp.tool(description="Lister les branches d'un dépôt Azure DevOps.")
async def azure_devops_list_branches(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_list_branches", inputs={"project": project, "repo": repo}):
        async with get_ado_client(effective_pat, org_url) as client:
            response = await client.get(
                f"/{project}/_apis/git/repositories/{repo}/refs?filter=heads/&{_API}"
            )
            await raise_for_status(response)
            data = response.json()
            return {
                "count": data.get("count", 0),
                "branches": [
                    {"name": r["name"].removeprefix("refs/heads/"), "commit_id": r["objectId"]}
                    for r in data.get("value", [])
                ],
            }


@mcp.tool(description="Créer une nouvelle branche dans un dépôt Azure DevOps à partir d'un commit existant.")
async def azure_devops_create_branch(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    branch_name: Annotated[str, Field(description="Nom de la nouvelle branche (sans 'refs/heads/')")],
    source_commit_id: Annotated[str, Field(description="ID du commit source (SHA) depuis lequel créer la branche")],
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_create_branch", inputs={"project": project, "repo": repo, "branch": branch_name}):
        async with get_ado_client(effective_pat, org_url) as client:
            payload = [
                {
                    "name": f"refs/heads/{branch_name}",
                    "newObjectId": source_commit_id,
                    "oldObjectId": "0000000000000000000000000000000000000000",
                }
            ]
            response = await client.post(
                f"/{project}/_apis/git/repositories/{repo}/refs?{_API}",
                json=payload,
            )
            await raise_for_status(response)
            data = response.json()
            results = data.get("value", [])
            if results and results[0].get("success"):
                return {"created": True, "branch": branch_name, "commit_id": source_commit_id}
            return {"created": False, "detail": results}


@mcp.tool(description="Lire le contenu d'un fichier dans un dépôt Azure DevOps à une branche ou commit donné.")
async def azure_devops_get_file(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    path: Annotated[str, Field(description="Chemin du fichier dans le dépôt (ex: /src/main.py)")],
    ref: Annotated[str, Field(description="Nom de la branche ou SHA du commit")] = "main",
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_get_file", inputs={"project": project, "repo": repo, "path": path}):
        async with get_ado_client(effective_pat, org_url) as client:
            params = (
                f"path={path}"
                f"&versionDescriptor.version={ref}"
                f"&versionDescriptor.versionType=branch"
                f"&$format=text"
                f"&{_API}"
            )
            response = await client.get(
                f"/{project}/_apis/git/repositories/{repo}/items?{params}"
            )
            await raise_for_status(response)
            return {"path": path, "ref": ref, "content": response.text}
