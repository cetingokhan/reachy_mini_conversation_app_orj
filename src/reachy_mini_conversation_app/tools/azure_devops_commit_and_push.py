import os
import asyncio
import logging
import subprocess
from typing import Any
from pathlib import Path

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class AzureDevOpsCommitAndPush(Tool):
    """Commit and push changes to an Azure DevOps repository."""

    name = "azure_devops_commit_and_push"
    description = "Commit and push changes to Azure DevOps repository."
    needs_response = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the repository.",
            },
            "commit_message": {
                "type": "string",
                "description": "Commit message.",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific files to stage. Stages all files when omitted.",
            },
        },
        "required": ["repo_path", "commit_message"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Commit and push changes to a repository."""
        repo_path_raw = kwargs.get("repo_path")
        commit_message_raw = kwargs.get("commit_message")
        files_raw = kwargs.get("files")

        if not isinstance(repo_path_raw, str) or not repo_path_raw.strip():
            logger.warning("azure_devops_commit_and_push: invalid repo_path")
            return {"error": "repo_path must be a non-empty string"}
        if not isinstance(commit_message_raw, str) or not commit_message_raw.strip():
            logger.warning("azure_devops_commit_and_push: invalid commit_message")
            return {"error": "commit_message must be a non-empty string"}
        if files_raw is not None and (
            not isinstance(files_raw, list) or any(not isinstance(file_path, str) for file_path in files_raw)
        ):
            logger.warning("azure_devops_commit_and_push: invalid files payload")
            return {"error": "files must be an array of strings"}

        repo_path = Path(os.path.expanduser(repo_path_raw)).resolve()
        commit_message = commit_message_raw.strip()
        files = [file_path for file_path in (files_raw or []) if file_path.strip()]

        if not repo_path.exists():
            logger.warning("azure_devops_commit_and_push: repo_path does not exist: %s", repo_path)
            return {"error": f"Repository path does not exist: {repo_path}"}
        if not repo_path.is_dir():
            logger.warning("azure_devops_commit_and_push: repo_path is not a directory: %s", repo_path)
            return {"error": f"Repository path is not a directory: {repo_path}"}

        logger.info(
            "Tool call: azure_devops_commit_and_push repo_path=%s file_count=%s",
            repo_path,
            len(files) if files else "all",
        )

        try:
            await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )

            add_command = ["git", "add", *files] if files else ["git", "add", "."]
            await asyncio.to_thread(
                subprocess.run,
                add_command,
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )

            await asyncio.to_thread(
                subprocess.run,
                ["git", "commit", "-m", commit_message],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )

            await asyncio.to_thread(
                subprocess.run,
                ["git", "push"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )

            branch_result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            output = error.stderr.strip() or error.stdout.strip() or str(error)
            logger.error("azure_devops_commit_and_push failed: %s", output)
            return {"error": output}
        except OSError as error:
            logger.error("azure_devops_commit_and_push OS error: %s", error)
            return {"error": f"Failed to run git command: {error}"}

        branch_name = branch_result.stdout.strip()
        logger.info("azure_devops_commit_and_push pushed branch=%s", branch_name)
        return {"status": "pushed", "branch": branch_name}
