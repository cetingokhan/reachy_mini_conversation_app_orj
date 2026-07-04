import os
import asyncio
import logging
import subprocess
from typing import Any
from pathlib import Path

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class AzureDevOpsCreateBranch(Tool):
    """Create and checkout a new branch in a local git repository."""

    name = "azure_devops_create_branch"
    description = "Create and checkout a new branch in a local git repository."
    needs_response = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the cloned repository.",
            },
            "branch_name": {
                "type": "string",
                "description": "Name of the new branch to create.",
            },
            "from_branch": {
                "type": "string",
                "description": "Source branch to branch from.",
                "default": "main",
            },
        },
        "required": ["repo_path", "branch_name"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Create and checkout a new git branch."""
        repo_path_raw = kwargs.get("repo_path")
        branch_name_raw = kwargs.get("branch_name")
        from_branch_raw = kwargs.get("from_branch", "main")

        if not isinstance(repo_path_raw, str) or not repo_path_raw.strip():
            return {"error": "repo_path must be a non-empty string"}
        if not isinstance(branch_name_raw, str) or not branch_name_raw.strip():
            return {"error": "branch_name must be a non-empty string"}
        if not isinstance(from_branch_raw, str) or not from_branch_raw.strip():
            return {"error": "from_branch must be a non-empty string"}

        repo_path = Path(os.path.expanduser(repo_path_raw)).resolve()
        branch_name = branch_name_raw.strip()
        from_branch = from_branch_raw.strip()

        logger.info(
            "Tool call: azure_devops_create_branch repo_path=%s branch_name=%s from_branch=%s",
            repo_path,
            branch_name,
            from_branch,
        )

        if not repo_path.exists():
            logger.error("azure_devops_create_branch failed: repo_path does not exist: %s", repo_path)
            return {"error": f"repo_path does not exist: {repo_path}"}
        if not repo_path.is_dir():
            logger.error("azure_devops_create_branch failed: repo_path is not a directory: %s", repo_path)
            return {"error": f"repo_path is not a directory: {repo_path}"}

        try:
            await asyncio.to_thread(
                subprocess.run,
                ["git", "checkout", from_branch],
                cwd=os.fspath(repo_path),
                capture_output=True,
                text=True,
                check=True,
            )
            await asyncio.to_thread(
                subprocess.run,
                ["git", "checkout", "-b", branch_name],
                cwd=os.fspath(repo_path),
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError as e:
            logger.error("azure_devops_create_branch failed: git is unavailable: %s", e)
            return {"error": f"git is unavailable: {e}"}
        except subprocess.CalledProcessError as e:
            command_output = e.stderr.strip() or e.stdout.strip() or str(e)
            logger.error("azure_devops_create_branch failed: %s", command_output)
            return {"error": f"git command failed: {command_output}"}
        except Exception as e:
            logger.error("azure_devops_create_branch failed: %s", e)
            return {"error": f"azure_devops_create_branch failed: {type(e).__name__}: {e}"}

        return {"status": "branch created", "branch": branch_name}
