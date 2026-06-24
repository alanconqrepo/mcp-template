from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.azure_devops_client import get_ado_client, raise_for_status, resolve_pat_and_org

_API = "api-version=7.1"
_PAT_FIELD = Field(description="PAT Azure DevOps. Utilise AZURE_DEVOPS_DEFAULT_PAT si absent.")


def _pr_summary(pr: dict) -> dict:
    return {
        "id": pr.get("pullRequestId"),
        "title": pr.get("title"),
        "status": pr.get("status"),
        "merge_status": pr.get("mergeStatus"),
        "source_branch": pr.get("sourceRefName", "").removeprefix("refs/heads/"),
        "target_branch": pr.get("targetRefName", "").removeprefix("refs/heads/"),
        "created_by": pr.get("createdBy", {}).get("displayName"),
        "creation_date": pr.get("creationDate"),
        "url": pr.get("url"),
    }


@mcp.tool(description="Lister les pull requests d'un dépôt Azure DevOps avec filtres optionnels.")
async def azure_devops_list_prs(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    status: Annotated[
        Literal["active", "completed", "abandoned", "all"],
        Field(description="Statut des PRs à retourner"),
    ] = "active",
    source_branch: Annotated[str | None, Field(description="Filtrer par branche source")] = None,
    target_branch: Annotated[str | None, Field(description="Filtrer par branche cible")] = None,
    top: Annotated[int, Field(description="Nombre maximum de PRs à retourner", ge=1, le=100)] = 25,
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_list_prs", inputs={"project": project, "repo": repo, "status": status}):
        async with get_ado_client(effective_pat, org_url) as client:
            params = f"searchCriteria.status={status}&$top={top}&{_API}"
            if source_branch:
                params += f"&searchCriteria.sourceRefName=refs/heads/{source_branch}"
            if target_branch:
                params += f"&searchCriteria.targetRefName=refs/heads/{target_branch}"
            response = await client.get(
                f"/{project}/_apis/git/repositories/{repo}/pullrequests?{params}"
            )
            await raise_for_status(response)
            data = response.json()
            return {
                "count": data.get("count", 0),
                "pull_requests": [_pr_summary(pr) for pr in data.get("value", [])],
            }


@mcp.tool(description="Obtenir les détails complets d'une pull request Azure DevOps (statut de merge, conflits, reviewers).")
async def azure_devops_get_pr(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    pr_id: Annotated[int, Field(description="Identifiant numérique de la pull request")],
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_get_pr", inputs={"project": project, "repo": repo, "pr_id": pr_id}):
        async with get_ado_client(effective_pat, org_url) as client:
            response = await client.get(
                f"/{project}/_apis/git/repositories/{repo}/pullrequests/{pr_id}?{_API}"
            )
            await raise_for_status(response)
            pr = response.json()
            return {
                **_pr_summary(pr),
                "description": pr.get("description"),
                "reviewers": [
                    {"name": r.get("displayName"), "vote": r.get("vote"), "is_required": r.get("isRequired", False)}
                    for r in pr.get("reviewers", [])
                ],
                "last_merge_source_commit": pr.get("lastMergeSourceCommit", {}).get("commitId"),
                "last_merge_target_commit": pr.get("lastMergeTargetCommit", {}).get("commitId"),
                "has_conflicts": pr.get("mergeStatus") == "conflicts",
            }


@mcp.tool(description="Créer une pull request dans un dépôt Azure DevOps.")
async def azure_devops_create_pr(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    title: Annotated[str, Field(description="Titre de la pull request")],
    source_branch: Annotated[str, Field(description="Branche source (sans 'refs/heads/')")],
    target_branch: Annotated[str, Field(description="Branche cible (sans 'refs/heads/')")],
    description: Annotated[str, Field(description="Description de la pull request")] = "",
    auto_complete: Annotated[bool, Field(description="Activer la complétion automatique après approbation")] = False,
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_create_pr", inputs={"project": project, "repo": repo, "source": source_branch, "target": target_branch}):
        async with get_ado_client(effective_pat, org_url) as client:
            payload: dict = {
                "title": title,
                "description": description,
                "sourceRefName": f"refs/heads/{source_branch}",
                "targetRefName": f"refs/heads/{target_branch}",
            }
            if auto_complete:
                payload["completionOptions"] = {"mergeStrategy": "squash", "deleteSourceBranch": False}
            response = await client.post(
                f"/{project}/_apis/git/repositories/{repo}/pullrequests?{_API}",
                json=payload,
            )
            await raise_for_status(response)
            return _pr_summary(response.json())


@mcp.tool(description="Compléter (merger) une pull request Azure DevOps dont tous les reviewers ont approuvé.")
async def azure_devops_complete_pr(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    pr_id: Annotated[int, Field(description="Identifiant numérique de la pull request")],
    merge_strategy: Annotated[
        Literal["noFastForward", "squash", "rebase", "rebaseMerge"],
        Field(description="Stratégie de merge"),
    ] = "noFastForward",
    delete_source_branch: Annotated[bool, Field(description="Supprimer la branche source après merge")] = False,
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_complete_pr", inputs={"project": project, "repo": repo, "pr_id": pr_id}):
        async with get_ado_client(effective_pat, org_url) as client:
            # Fetch current PR to get lastMergeSourceCommit (required by ADO API)
            get_response = await client.get(
                f"/{project}/_apis/git/repositories/{repo}/pullrequests/{pr_id}?{_API}"
            )
            await raise_for_status(get_response)
            pr = get_response.json()
            last_merge_commit = pr.get("lastMergeSourceCommit", {}).get("commitId")
            if not last_merge_commit:
                raise RuntimeError("Impossible de récupérer lastMergeSourceCommit — la PR est peut-être déjà mergée ou en conflit.")

            patch_payload = {
                "status": "completed",
                "lastMergeSourceCommit": {"commitId": last_merge_commit},
                "completionOptions": {
                    "mergeStrategy": merge_strategy,
                    "deleteSourceBranch": delete_source_branch,
                },
            }
            patch_response = await client.patch(
                f"/{project}/_apis/git/repositories/{repo}/pullrequests/{pr_id}?{_API}",
                json=patch_payload,
            )
            await raise_for_status(patch_response)
            return _pr_summary(patch_response.json())


@mcp.tool(
    description=(
        "Analyser les conflits d'une pull request Azure DevOps. "
        "Retourne la liste des fichiers en conflit, leur type de conflit (content, rename, delete), "
        "et une synthèse pour aider à la résolution."
    )
)
async def azure_devops_analyze_conflicts(
    project: Annotated[str, Field(description="Nom du projet Azure DevOps")],
    repo: Annotated[str, Field(description="Nom ou ID du dépôt")],
    pr_id: Annotated[int, Field(description="Identifiant numérique de la pull request")],
    pat: Annotated[str | None, _PAT_FIELD] = None,
) -> dict:
    effective_pat, org_url = resolve_pat_and_org(pat)
    async with trace_tool("azure_devops_analyze_conflicts", inputs={"project": project, "repo": repo, "pr_id": pr_id}):
        async with get_ado_client(effective_pat, org_url) as client:
            # Get PR metadata first for context
            pr_response = await client.get(
                f"/{project}/_apis/git/repositories/{repo}/pullrequests/{pr_id}?{_API}"
            )
            await raise_for_status(pr_response)
            pr = pr_response.json()

            merge_status = pr.get("mergeStatus")
            source = pr.get("sourceRefName", "").removeprefix("refs/heads/")
            target = pr.get("targetRefName", "").removeprefix("refs/heads/")

            if merge_status != "conflicts":
                return {
                    "pr_id": pr_id,
                    "has_conflicts": False,
                    "merge_status": merge_status,
                    "source_branch": source,
                    "target_branch": target,
                    "message": f"Aucun conflit détecté. Statut de merge : {merge_status}.",
                }

            # Fetch conflict details
            conflicts_response = await client.get(
                f"/{project}/_apis/git/repositories/{repo}/pullrequests/{pr_id}/conflicts?{_API}"
            )
            await raise_for_status(conflicts_response)
            conflicts_data = conflicts_response.json()
            raw_conflicts = conflicts_data.get("value", [])

            parsed = []
            for c in raw_conflicts:
                conflict_type = c.get("conflictType", "unknown")
                source_item = c.get("sourceCommitItem") or c.get("ourChange", {}).get("item", {})
                target_item = c.get("targetCommitItem") or c.get("theirChange", {}).get("item", {})
                parsed.append({
                    "conflict_id": c.get("conflictId"),
                    "conflict_type": conflict_type,
                    "path": source_item.get("path") or target_item.get("path", "?"),
                    "resolution_status": c.get("resolutionStatus", "unresolved"),
                })

            return {
                "pr_id": pr_id,
                "has_conflicts": True,
                "source_branch": source,
                "target_branch": target,
                "conflict_count": len(parsed),
                "conflicts": parsed,
                "summary": (
                    f"{len(parsed)} fichier(s) en conflit entre '{source}' et '{target}'. "
                    "Résolution requise avant de pouvoir compléter la PR."
                ),
            }
