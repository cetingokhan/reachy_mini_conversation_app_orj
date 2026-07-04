import os
import json
import logging
from typing import Any

import httpx

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class AzureDevOpsCreatePR(Tool):
    """Create a pull request in Azure DevOps."""

    name = "azure_devops_create_pr"
    description = "Create a pull request in Azure DevOps."
    needs_response = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "organization": {
                "type": "string",
                "description": "Azure DevOps organization",
            },
            "project": {
                "type": "string",
                "description": "Project name",
            },
            "repo_name": {
                "type": "string",
                "description": "Repository name",
            },
            "source_branch": {
                "type": "string",
                "description": "Feature branch",
            },
            "target_branch": {
                "type": "string",
                "description": "Target branch",
                "default": "development",
            },
            "title": {
                "type": "string",
                "description": "PR title",
            },
            "description": {
                "type": "string",
                "description": "PR description",
            },
            "reviewers": {
                "type": "array",
                "description": "Reviewer emails",
                "items": {"type": "string"},
            },
        },
        "required": [
            "organization",
            "project",
            "repo_name",
            "source_branch",
            "title",
            "description",
        ],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Create a pull request in Azure DevOps."""
        del deps

        organization_raw = kwargs.get("organization")
        project = kwargs.get("project")
        repo_name = kwargs.get("repo_name")
        source_branch = kwargs.get("source_branch")
        target_branch = kwargs.get("target_branch", "development")
        title = kwargs.get("title")
        pull_request_description = kwargs.get("description")
        reviewers_raw = kwargs.get("reviewers", [])

        if not isinstance(organization_raw, str) or not organization_raw.strip():
            logger.warning("azure_devops_create_pr: invalid organization")
            return {"error": "organization must be a non-empty string"}
        if not isinstance(project, str) or not project.strip():
            logger.warning("azure_devops_create_pr: invalid project")
            return {"error": "project must be a non-empty string"}
        if not isinstance(repo_name, str) or not repo_name.strip():
            logger.warning("azure_devops_create_pr: invalid repo_name")
            return {"error": "repo_name must be a non-empty string"}
        if not isinstance(source_branch, str) or not source_branch.strip():
            logger.warning("azure_devops_create_pr: invalid source_branch")
            return {"error": "source_branch must be a non-empty string"}
        if not isinstance(target_branch, str) or not target_branch.strip():
            logger.warning("azure_devops_create_pr: invalid target_branch")
            return {"error": "target_branch must be a non-empty string"}
        if not isinstance(title, str) or not title.strip():
            logger.warning("azure_devops_create_pr: invalid title")
            return {"error": "title must be a non-empty string"}
        if not isinstance(pull_request_description, str) or not pull_request_description.strip():
            logger.warning("azure_devops_create_pr: invalid description")
            return {"error": "description must be a non-empty string"}

        organization_input = organization_raw.strip()
        project_name = project.strip()
        repository_name = repo_name.strip()
        source_branch_name = source_branch.strip()
        target_branch_name = target_branch.strip()
        pull_request_title = title.strip()
        pull_request_body = pull_request_description.strip()

        if not isinstance(reviewers_raw, list) or any(
            not isinstance(reviewer, str) or not reviewer.strip() for reviewer in reviewers_raw
        ):
            logger.warning("azure_devops_create_pr: invalid reviewers payload")
            return {"error": "reviewers must be an array of non-empty strings"}

        pat = os.getenv("AZURE_DEVOPS_PAT")
        env_organization = os.getenv("AZURE_DEVOPS_ORG")
        if not pat:
            logger.warning("azure_devops_create_pr: missing AZURE_DEVOPS_PAT")
            return {"error": "AZURE_DEVOPS_PAT is not configured"}

        organization = env_organization or organization_input
        if env_organization and env_organization != organization_input:
            logger.warning(
                "azure_devops_create_pr: using AZURE_DEVOPS_ORG=%s instead of organization=%s",
                env_organization,
                organization_input,
            )

        source_ref_name = (
            source_branch_name if source_branch_name.startswith("refs/") else f"refs/heads/{source_branch_name}"
        )
        target_ref_name = (
            target_branch_name if target_branch_name.startswith("refs/") else f"refs/heads/{target_branch_name}"
        )

        request_body: dict[str, Any] = {
            "sourceRefName": source_ref_name,
            "targetRefName": target_ref_name,
            "title": pull_request_title,
            "description": pull_request_body,
        }

        headers = {"Content-Type": "application/json"}
        auth = httpx.BasicAuth(username="", password=pat)

        try:
            with httpx.Client(auth=auth, headers=headers, timeout=15.0) as client:
                reviewers: list[dict[str, str]] = []
                for reviewer in reviewers_raw:
                    identity_response = client.get(
                        f"https://vssps.dev.azure.com/{organization}/_apis/identities",
                        params={
                            "searchFilter": "General",
                            "filterValue": reviewer,
                            "queryMembership": "None",
                            "api-version": "7.1-preview.1",
                        },
                    )
                    identity_response.raise_for_status()
                    identity_payload = identity_response.json()
                    identities = identity_payload.get("value")
                    if not isinstance(identities, list) or not identities:
                        logger.warning("azure_devops_create_pr: reviewer not found: %s", reviewer)
                        return {"error": f"Reviewer not found: {reviewer}"}

                    first_identity = identities[0]
                    if not isinstance(first_identity, dict):
                        logger.warning("azure_devops_create_pr: invalid reviewer response for %s", reviewer)
                        return {"error": f"Invalid reviewer lookup response for: {reviewer}"}

                    reviewer_id = first_identity.get("id")
                    if not isinstance(reviewer_id, str) or not reviewer_id:
                        logger.warning("azure_devops_create_pr: reviewer id missing for %s", reviewer)
                        return {"error": f"Reviewer id missing for: {reviewer}"}

                    reviewers.append({"id": reviewer_id, "uniqueName": reviewer})

                if reviewers:
                    request_body["reviewers"] = reviewers

                logger.info(
                    "Tool call: azure_devops_create_pr org=%s project=%s repo=%s source=%s target=%s reviewers=%s",
                    organization,
                    project_name,
                    repository_name,
                    source_branch_name,
                    target_branch_name,
                    json.dumps(reviewers_raw),
                )
                response = client.post(
                    f"https://dev.azure.com/{organization}/{project_name}/_apis/git/repositories/{repository_name}/pullrequests",
                    params={"api-version": "7.2-preview.2"},
                    json=request_body,
                )
                response.raise_for_status()

            response_payload = response.json()
        except httpx.HTTPStatusError as error:
            response_text = error.response.text.strip()
            logger.error("azure_devops_create_pr request failed: %s", response_text or error)
            return {"error": f"Azure DevOps API request failed: {response_text or str(error)}"}
        except httpx.RequestError as error:
            logger.error("azure_devops_create_pr network failure: %s", error)
            return {"error": f"Azure DevOps request failed: {error}"}
        except json.JSONDecodeError as error:
            logger.error("azure_devops_create_pr invalid JSON response: %s", error)
            return {"error": "Azure DevOps returned an invalid JSON response"}
        except Exception as error:
            logger.exception("azure_devops_create_pr failed")
            return {"error": f"azure_devops_create_pr failed: {type(error).__name__}: {error}"}

        pr_id = response_payload.get("pullRequestId")
        if not isinstance(pr_id, int):
            logger.warning("azure_devops_create_pr: missing pullRequestId in response")
            return {"error": "Azure DevOps response did not include pullRequestId"}

        pr_url = response_payload.get("remoteUrl")
        if not isinstance(pr_url, str) or not pr_url:
            links = response_payload.get("_links")
            if isinstance(links, dict):
                web_link = links.get("web")
                if isinstance(web_link, dict):
                    href = web_link.get("href")
                    if isinstance(href, str) and href:
                        pr_url = href
        if not isinstance(pr_url, str) or not pr_url:
            fallback_url = response_payload.get("url")
            pr_url = fallback_url if isinstance(fallback_url, str) else ""

        return {
            "status": "pr_created",
            "pr_id": pr_id,
            "url": pr_url,
        }
