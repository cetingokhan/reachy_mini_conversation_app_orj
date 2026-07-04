from enum import Enum


class ToolState(Enum):
    """Status of a background tool."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SystemTool(Enum):
    """System tools are tools that are used to manage the background tool manager."""

    TASK_STATUS = "task_status"
    TASK_CANCEL = "task_cancel"


AZURE_DEVOPS_TOOL_NAMES = (
    "azure_devops_clone_repo",
    "azure_devops_create_branch",
    "azure_devops_commit_and_push",
    "azure_devops_create_pr",
    "azure_devops_trigger_codedev",
)
