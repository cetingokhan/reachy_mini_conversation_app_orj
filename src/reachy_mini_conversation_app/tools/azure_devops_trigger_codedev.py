import os
import uuid
import logging
import subprocess
from typing import Any

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class AzureDevOpsTriggerCodeDev(Tool):
    """Trigger async code development via Copilot CLI sub-agent."""

    name = "azure_devops_trigger_codedev"
    description = "Trigger async code development via Copilot CLI sub-agent."
    needs_response = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "description": "Azure DevOps repository URL.",
            },
            "task_description": {
                "type": "string",
                "description": "What code should be implemented.",
            },
            "target_branch": {
                "type": "string",
                "description": "Branch to commit changes to.",
            },
            "instructions_file": {
                "type": "string",
                "description": "Optional path to a file with detailed instructions.",
            },
        },
        "required": ["repo_url", "task_description", "target_branch"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Spawn a Copilot CLI task and return its task ID."""
        del deps

        repo_url = kwargs.get("repo_url")
        task_description = kwargs.get("task_description")
        target_branch = kwargs.get("target_branch")
        instructions_file = kwargs.get("instructions_file")

        if not isinstance(repo_url, str) or not repo_url.strip():
            return {"error": "repo_url must be a non-empty string"}
        if not isinstance(task_description, str) or not task_description.strip():
            return {"error": "task_description must be a non-empty string"}
        if not isinstance(target_branch, str) or not target_branch.strip():
            return {"error": "target_branch must be a non-empty string"}
        if instructions_file is not None and not isinstance(instructions_file, str):
            return {"error": "instructions_file must be a string"}

        env = os.environ.copy()
        if not env.get("GITHUB_COPILOT_CLI_TOKEN"):
            return {"error": "GITHUB_COPILOT_CLI_TOKEN is not set"}

        full_task_description = task_description.strip()
        if instructions_file:
            if not os.path.isfile(instructions_file):
                return {"error": f"instructions_file not found: {instructions_file}"}
            try:
                with open(instructions_file, encoding="utf-8") as instructions_handle:
                    instructions = instructions_handle.read().strip()
            except OSError as error:
                logger.warning("Failed to read instructions file %s: %s", instructions_file, error)
                return {"error": f"Failed to read instructions file: {error}"}
            if instructions:
                full_task_description = (
                    f"{full_task_description}\n\nDetailed instructions from {instructions_file}:\n{instructions}"
                )

        task_id = f"codedev_{uuid.uuid4()}"
        command = [
            "copilot",
            "task",
            "--repo",
            repo_url.strip(),
            "--branch",
            target_branch.strip(),
            "--task",
            full_task_description,
        ]

        popen_kwargs: dict[str, Any] = {
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            popen_kwargs["start_new_session"] = True

        try:
            subprocess.Popen(command, **popen_kwargs)
        except OSError as error:
            logger.warning("Failed to spawn sub-agent task_id=%s: %s", task_id, error)
            return {"error": f"Failed to spawn: {error}"}

        logger.info("Spawned sub-agent task_id=%s", task_id)
        return {"status": "task_queued", "task_id": task_id}
