import os
import asyncio
import logging
import subprocess
from pathlib import Path
from urllib.parse import quote

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class AzureDevOpsCloneRepo(Tool):
    """Clone an Azure DevOps repository locally."""

    name = "azure_devops_clone_repo"
    description = "Clone an Azure DevOps repository locally using PAT authentication."
    needs_response = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "organization": {
                "type": "string",
                "description": "Azure DevOps organization name.",
            },
            "project": {
                "type": "string",
                "description": "Azure DevOps project name.",
            },
            "repo_name": {
                "type": "string",
                "description": "Azure DevOps repository name.",
            },
            "branch": {
                "type": "string",
                "description": "Branch to clone.",
                "default": "main",
            },
            "target_path": {
                "type": "string",
                "description": "Optional destination path for the cloned repository.",
            },
        },
        "required": ["organization", "project", "repo_name"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: object) -> dict[str, object]:
        """Clone an Azure DevOps repository locally."""
        organization = kwargs.get("organization")
        project = kwargs.get("project")
        repo_name = kwargs.get("repo_name")
        branch = kwargs.get("branch", "main")
        target_path = kwargs.get("target_path")

        if not isinstance(organization, str) or not organization.strip():
            return {"error": "organization must be a non-empty string"}
        if not isinstance(project, str) or not project.strip():
            return {"error": "project must be a non-empty string"}
        if not isinstance(repo_name, str) or not repo_name.strip():
            return {"error": "repo_name must be a non-empty string"}
        if not isinstance(branch, str) or not branch.strip():
            return {"error": "branch must be a non-empty string"}
        if target_path is not None and not isinstance(target_path, str):
            return {"error": "target_path must be a string when provided"}

        pat = os.environ.get("AZURE_DEVOPS_PAT")
        if not pat:
            logger.error("azure_devops_clone_repo failed: missing AZURE_DEVOPS_PAT")
            return {"error": "AZURE_DEVOPS_PAT is not set"}

        destination = Path(target_path).expanduser() if target_path else None
        if destination is None:
            base_path = Path(deps.instance_path).expanduser() if deps.instance_path else Path.cwd()
            destination = base_path / "cloned_repos" / repo_name
        elif not destination.is_absolute():
            destination = Path.cwd() / destination
        destination_parent = destination.parent

        try:
            destination_parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            logger.error("azure_devops_clone_repo failed to prepare %s: %s", destination_parent, error)
            return {"error": f"failed to prepare destination: {error}"}

        encoded_pat = quote(pat, safe="")
        authenticated_url = (
            f"https://{encoded_pat}@dev.azure.com/"
            f"{quote(organization, safe='')}/{quote(project, safe='')}/_git/{quote(repo_name, safe='')}"
        )
        command = [
            "git",
            "clone",
            "--branch",
            branch,
            "--single-branch",
            authenticated_url,
            str(destination),
        ]

        logger.info(
            "Tool call: azure_devops_clone_repo org=%s project=%s repo=%s branch=%s target=%s",
            organization,
            project,
            repo_name,
            branch,
            destination,
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            logger.error("azure_devops_clone_repo failed to start git: %s", error)
            return {"error": f"failed to start git clone: {error}"}
        except Exception as error:
            logger.error("azure_devops_clone_repo failed unexpectedly: %s", error)
            return {"error": f"git clone failed unexpectedly: {error}"}

        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "git clone failed"
            safe_error = stderr.replace(pat, "***").replace(encoded_pat, "***")
            logger.error("azure_devops_clone_repo failed: %s", safe_error)
            return {"error": safe_error}

        cloned_path = str(destination.resolve())
        logger.info("azure_devops_clone_repo cloned %s to %s", repo_name, cloned_path)
        return {"status": "cloned", "path": cloned_path}
