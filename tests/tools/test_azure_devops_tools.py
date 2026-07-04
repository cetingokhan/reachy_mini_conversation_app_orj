import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

import reachy_mini_conversation_app.tools.azure_devops_create_pr as create_pr_module
import reachy_mini_conversation_app.tools.azure_devops_trigger_codedev as trigger_codedev_module
from reachy_mini_conversation_app.tools import AzureDevOpsCreatePR as ExportedAzureDevOpsCreatePR
from reachy_mini_conversation_app.tools import (
    AzureDevOpsCloneRepo as ExportedAzureDevOpsCloneRepo,
)
from reachy_mini_conversation_app.tools import (
    AzureDevOpsCreateBranch as ExportedAzureDevOpsCreateBranch,
)
from reachy_mini_conversation_app.tools import (
    AzureDevOpsCommitAndPush as ExportedAzureDevOpsCommitAndPush,
)
from reachy_mini_conversation_app.tools import (
    AzureDevOpsTriggerCodeDev as ExportedAzureDevOpsTriggerCodeDev,
)
from reachy_mini_conversation_app.tools.core_tools import ToolDependencies
from reachy_mini_conversation_app.tools.tool_constants import AZURE_DEVOPS_TOOL_NAMES
from reachy_mini_conversation_app.tools.azure_devops_create_pr import AzureDevOpsCreatePR
from reachy_mini_conversation_app.tools.azure_devops_clone_repo import AzureDevOpsCloneRepo
from reachy_mini_conversation_app.tools.azure_devops_create_branch import AzureDevOpsCreateBranch
from reachy_mini_conversation_app.tools.azure_devops_commit_and_push import AzureDevOpsCommitAndPush
from reachy_mini_conversation_app.tools.azure_devops_trigger_codedev import AzureDevOpsTriggerCodeDev


@pytest.fixture(name="reachy_mini")
def _reachy_mini() -> MagicMock:
    return MagicMock()


@pytest.fixture(name="movement_manager")
def _movement_manager() -> MagicMock:
    return MagicMock()


@pytest.fixture(name="deps")
def _deps(reachy_mini: MagicMock, movement_manager: MagicMock, tmp_path: Path) -> ToolDependencies:
    return ToolDependencies(reachy_mini=reachy_mini, movement_manager=movement_manager, instance_path=tmp_path)


def _completed_process(*, stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr=stderr)


def _httpx_json_response(status_code: int, url: str, payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=httpx.Request("POST", url),
        content=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


class _FakeAzureDevOpsClient:
    def __init__(
        self,
        *,
        get_responses: list[httpx.Response] | None = None,
        post_response: httpx.Response,
        get_calls: list[dict[str, object]],
        post_calls: list[dict[str, object]],
        **kwargs: object,
    ) -> None:
        self._get_responses = list(get_responses or [])
        self._post_response = post_response
        self.get_calls = get_calls
        self.post_calls = post_calls
        self.kwargs = kwargs

    def __enter__(self) -> "_FakeAzureDevOpsClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def get(self, url: str, *, params: dict[str, str]) -> httpx.Response:
        self.get_calls.append({"url": url, "params": params})
        return self._get_responses.pop(0)

    def post(self, url: str, *, params: dict[str, str], json: dict[str, object]) -> httpx.Response:
        self.post_calls.append({"url": url, "params": params, "json": json})
        return self._post_response


def test_azure_devops_tools_are_exported_for_package_imports() -> None:
    """The tools package should re-export Azure DevOps tools for auto-discovery imports."""
    assert ExportedAzureDevOpsCloneRepo is AzureDevOpsCloneRepo
    assert ExportedAzureDevOpsCreateBranch is AzureDevOpsCreateBranch
    assert ExportedAzureDevOpsCommitAndPush is AzureDevOpsCommitAndPush
    assert ExportedAzureDevOpsCreatePR is AzureDevOpsCreatePR
    assert ExportedAzureDevOpsTriggerCodeDev is AzureDevOpsTriggerCodeDev
    assert AZURE_DEVOPS_TOOL_NAMES == (
        "azure_devops_clone_repo",
        "azure_devops_create_branch",
        "azure_devops_commit_and_push",
        "azure_devops_create_pr",
        "azure_devops_trigger_codedev",
    )


@pytest.mark.asyncio
async def test_azure_devops_clone_repo_clones_successfully(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies, tmp_path: Path
) -> None:
    """Clone should report the resolved destination on success."""
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "test-pat")
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return _completed_process()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = await AzureDevOpsCloneRepo()(
        deps, organization="org", project="proj", repo_name="robot-app", branch="main"
    )

    expected_path = str((tmp_path / "cloned_repos" / "robot-app").resolve())
    assert result == {"status": "cloned", "path": expected_path}
    assert calls == [
        (
            [
                "git",
                "clone",
                "--branch",
                "main",
                "--single-branch",
                "https://test-pat@dev.azure.com/org/proj/_git/robot-app",
                expected_path,
            ],
            {"capture_output": True, "text": True, "check": False},
        )
    ]


@pytest.mark.asyncio
async def test_azure_devops_clone_repo_returns_error_when_git_clone_fails(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies
) -> None:
    """Clone should surface git errors without exposing the PAT."""
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "secret-pat")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _completed_process(
            returncode=128, stderr="fatal: could not read from remote repository"
        ),
    )

    result = await AzureDevOpsCloneRepo()(deps, organization="org", project="proj", repo_name="robot-app")

    assert result == {"error": "fatal: could not read from remote repository"}


@pytest.mark.asyncio
async def test_azure_devops_clone_repo_returns_error_when_pat_missing(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies
) -> None:
    """Clone should fail fast when the Azure DevOps PAT is unset."""
    monkeypatch.delenv("AZURE_DEVOPS_PAT", raising=False)

    result = await AzureDevOpsCloneRepo()(deps, organization="org", project="proj", repo_name="robot-app")

    assert result == {"error": "AZURE_DEVOPS_PAT is not set"}


@pytest.mark.asyncio
async def test_azure_devops_create_branch_creates_branch_successfully(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies, tmp_path: Path
) -> None:
    """Branch creation should check out the source branch then create the target branch."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return _completed_process()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = await AzureDevOpsCreateBranch()(
        deps,
        repo_path=str(repo_path),
        branch_name="feature/new-tool",
        from_branch="develop",
    )

    assert result == {"status": "branch created", "branch": "feature/new-tool"}
    assert calls == [
        (
            ["git", "checkout", "develop"],
            {"cwd": str(repo_path.resolve()), "capture_output": True, "text": True, "check": True},
        ),
        (
            ["git", "checkout", "-b", "feature/new-tool"],
            {"cwd": str(repo_path.resolve()), "capture_output": True, "text": True, "check": True},
        ),
    ]


@pytest.mark.asyncio
async def test_azure_devops_create_branch_returns_error_when_repo_path_missing(
    deps: ToolDependencies, tmp_path: Path
) -> None:
    """Branch creation should reject missing repositories."""
    missing_path = tmp_path / "missing-repo"

    result = await AzureDevOpsCreateBranch()(deps, repo_path=str(missing_path), branch_name="feature/new-tool")

    assert result == {"error": f"repo_path does not exist: {missing_path.resolve()}"}


@pytest.mark.asyncio
async def test_azure_devops_create_branch_returns_error_when_git_checkout_fails(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies, tmp_path: Path
) -> None:
    """Branch creation should surface checkout failures."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, command, stderr="pathspec did not match any file(s) known to git")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = await AzureDevOpsCreateBranch()(deps, repo_path=str(repo_path), branch_name="feature/new-tool")

    assert result == {"error": "git command failed: pathspec did not match any file(s) known to git"}


@pytest.mark.asyncio
async def test_azure_devops_commit_and_push_pushes_changes_successfully(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies, tmp_path: Path
) -> None:
    """Commit and push should stage all files when no file list is provided."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    calls: list[tuple[list[str], dict[str, object]]] = []
    responses = iter(
        [
            _completed_process(stdout="true\n"),
            _completed_process(),
            _completed_process(),
            _completed_process(),
            _completed_process(stdout="feature/new-tool\n"),
        ]
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return next(responses)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = await AzureDevOpsCommitAndPush()(deps, repo_path=str(repo_path), commit_message="Add Azure DevOps tests")

    assert result == {"status": "pushed", "branch": "feature/new-tool"}
    assert calls[1][0] == ["git", "add", "."]
    assert calls[3][0] == ["git", "push"]


@pytest.mark.asyncio
async def test_azure_devops_commit_and_push_returns_error_when_repo_path_missing(
    deps: ToolDependencies, tmp_path: Path
) -> None:
    """Commit and push should reject missing repositories."""
    missing_path = tmp_path / "missing-repo"

    result = await AzureDevOpsCommitAndPush()(
        deps,
        repo_path=str(missing_path),
        commit_message="Add Azure DevOps tests",
    )

    assert result == {"error": f"Repository path does not exist: {missing_path.resolve()}"}


@pytest.mark.asyncio
async def test_azure_devops_commit_and_push_returns_error_when_git_push_fails(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies, tmp_path: Path
) -> None:
    """Commit and push should surface git push failures."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    responses = iter(
        [
            _completed_process(stdout="true\n"),
            _completed_process(),
            _completed_process(),
        ]
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command == ["git", "push"]:
            raise subprocess.CalledProcessError(1, command, stderr="failed to push some refs")
        return next(responses)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = await AzureDevOpsCommitAndPush()(deps, repo_path=str(repo_path), commit_message="Push changes")

    assert result == {"error": "failed to push some refs"}


@pytest.mark.asyncio
async def test_azure_devops_commit_and_push_stages_specific_files(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies, tmp_path: Path
) -> None:
    """Commit and push should stage only the requested files when provided."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    calls: list[list[str]] = []
    responses = iter(
        [
            _completed_process(stdout="true\n"),
            _completed_process(),
            _completed_process(),
            _completed_process(),
            _completed_process(stdout="feature/files-only\n"),
        ]
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return next(responses)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = await AzureDevOpsCommitAndPush()(
        deps,
        repo_path=str(repo_path),
        commit_message="Stage selected files",
        files=["src/tool.py", "tests/test_tool.py"],
    )

    assert result == {"status": "pushed", "branch": "feature/files-only"}
    assert calls[1] == ["git", "add", "src/tool.py", "tests/test_tool.py"]


@pytest.mark.asyncio
async def test_azure_devops_create_pr_creates_pull_request(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies
) -> None:
    """Create PR should send the expected payload and return the created PR metadata."""
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "test-pat")
    monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
    get_calls: list[dict[str, object]] = []
    post_calls: list[dict[str, object]] = []
    post_response = _httpx_json_response(
        201,
        "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullrequests",
        {
            "pullRequestId": 123,
            "remoteUrl": "https://dev.azure.com/org/proj/_git/repo/pullrequest/123",
        },
    )
    monkeypatch.setattr(
        create_pr_module.httpx,
        "Client",
        lambda **kwargs: _FakeAzureDevOpsClient(
            get_responses=[],
            post_response=post_response,
            get_calls=get_calls,
            post_calls=post_calls,
            **kwargs,
        ),
    )

    result = await AzureDevOpsCreatePR()(
        deps,
        organization="org",
        project="proj",
        repo_name="repo",
        source_branch="feature/new-tool",
        target_branch="main",
        title="Add Azure DevOps tool tests",
        description="Adds regression coverage.",
    )

    assert result == {
        "status": "pr_created",
        "pr_id": 123,
        "url": "https://dev.azure.com/org/proj/_git/repo/pullrequest/123",
    }
    assert get_calls == []
    assert post_calls == [
        {
            "url": "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullrequests",
            "params": {"api-version": "7.2-preview.2"},
            "json": {
                "sourceRefName": "refs/heads/feature/new-tool",
                "targetRefName": "refs/heads/main",
                "title": "Add Azure DevOps tool tests",
                "description": "Adds regression coverage.",
            },
        }
    ]


@pytest.mark.asyncio
async def test_azure_devops_create_pr_returns_error_when_pat_missing(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies
) -> None:
    """Create PR should fail fast when the Azure DevOps PAT is unset."""
    monkeypatch.delenv("AZURE_DEVOPS_PAT", raising=False)
    monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)

    result = await AzureDevOpsCreatePR()(
        deps,
        organization="org",
        project="proj",
        repo_name="repo",
        source_branch="feature/new-tool",
        target_branch="main",
        title="Add Azure DevOps tool tests",
        description="Adds regression coverage.",
    )

    assert result == {"error": "AZURE_DEVOPS_PAT is not configured"}


@pytest.mark.asyncio
async def test_azure_devops_create_pr_returns_error_when_api_returns_400(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies
) -> None:
    """Create PR should surface Azure DevOps API validation failures."""
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "test-pat")
    monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
    get_calls: list[dict[str, object]] = []
    post_calls: list[dict[str, object]] = []
    post_response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullrequests"),
        content=b"TF401179: The pull request is invalid.",
    )
    monkeypatch.setattr(
        create_pr_module.httpx,
        "Client",
        lambda **kwargs: _FakeAzureDevOpsClient(
            get_responses=[],
            post_response=post_response,
            get_calls=get_calls,
            post_calls=post_calls,
            **kwargs,
        ),
    )

    result = await AzureDevOpsCreatePR()(
        deps,
        organization="org",
        project="proj",
        repo_name="repo",
        source_branch="feature/new-tool",
        target_branch="main",
        title="Add Azure DevOps tool tests",
        description="Adds regression coverage.",
    )

    assert result == {"error": "Azure DevOps API request failed: TF401179: The pull request is invalid."}


@pytest.mark.asyncio
async def test_azure_devops_create_pr_includes_optional_reviewers(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies
) -> None:
    """Create PR should resolve reviewer identities before sending the PR request."""
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "test-pat")
    monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
    get_calls: list[dict[str, object]] = []
    post_calls: list[dict[str, object]] = []
    reviewer_lookup_one = _httpx_json_response(
        200,
        "https://vssps.dev.azure.com/org/_apis/identities",
        {"value": [{"id": "reviewer-id-1"}]},
    )
    reviewer_lookup_two = _httpx_json_response(
        200,
        "https://vssps.dev.azure.com/org/_apis/identities",
        {"value": [{"id": "reviewer-id-2"}]},
    )
    post_response = _httpx_json_response(
        201,
        "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullrequests",
        {
            "pullRequestId": 123,
            "remoteUrl": "https://dev.azure.com/org/proj/_git/repo/pullrequest/123",
        },
    )
    monkeypatch.setattr(
        create_pr_module.httpx,
        "Client",
        lambda **kwargs: _FakeAzureDevOpsClient(
            get_responses=[reviewer_lookup_one, reviewer_lookup_two],
            post_response=post_response,
            get_calls=get_calls,
            post_calls=post_calls,
            **kwargs,
        ),
    )

    result = await AzureDevOpsCreatePR()(
        deps,
        organization="org",
        project="proj",
        repo_name="repo",
        source_branch="feature/new-tool",
        target_branch="main",
        title="Add Azure DevOps tool tests",
        description="Adds regression coverage.",
        reviewers=["alice@example.com", "bob@example.com"],
    )

    assert result == {
        "status": "pr_created",
        "pr_id": 123,
        "url": "https://dev.azure.com/org/proj/_git/repo/pullrequest/123",
    }
    assert len(get_calls) == 2
    assert post_calls[0]["json"]["reviewers"] == [
        {"id": "reviewer-id-1", "uniqueName": "alice@example.com"},
        {"id": "reviewer-id-2", "uniqueName": "bob@example.com"},
    ]


@pytest.mark.asyncio
async def test_azure_devops_trigger_codedev_spawns_non_blocking_subprocess(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies
) -> None:
    """Trigger CodeDev should queue a detached subprocess and return its task id."""
    monkeypatch.setenv("GITHUB_COPILOT_CLI_TOKEN", "token")
    process = MagicMock()
    popen_calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(command: list[str], **kwargs: object) -> MagicMock:
        popen_calls.append((command, kwargs))
        return process

    monkeypatch.setattr(trigger_codedev_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(trigger_codedev_module.uuid, "uuid4", lambda: "1234")

    result = await AzureDevOpsTriggerCodeDev()(
        deps,
        repo_url="https://dev.azure.com/org/proj/_git/repo",
        task_description="Add comprehensive tests.",
        target_branch="feature/new-tool",
    )

    assert result == {"status": "task_queued", "task_id": "codedev_1234"}
    assert popen_calls[0][0] == [
        "copilot",
        "task",
        "--repo",
        "https://dev.azure.com/org/proj/_git/repo",
        "--branch",
        "feature/new-tool",
        "--task",
        "Add comprehensive tests.",
    ]
    process.wait.assert_not_called()
    process.communicate.assert_not_called()


@pytest.mark.asyncio
async def test_azure_devops_trigger_codedev_returns_error_when_token_missing(
    monkeypatch: pytest.MonkeyPatch, deps: ToolDependencies
) -> None:
    """Trigger CodeDev should fail fast when the Copilot CLI token is unset."""
    monkeypatch.delenv("GITHUB_COPILOT_CLI_TOKEN", raising=False)

    result = await AzureDevOpsTriggerCodeDev()(
        deps,
        repo_url="https://dev.azure.com/org/proj/_git/repo",
        task_description="Add comprehensive tests.",
        target_branch="feature/new-tool",
    )

    assert result == {"error": "GITHUB_COPILOT_CLI_TOKEN is not set"}
