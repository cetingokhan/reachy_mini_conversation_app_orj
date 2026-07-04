from typing import Literal
from unittest.mock import MagicMock

import httpx
import pytest

from reachy_mini_conversation_app.tools.core_tools import ToolDependencies
from reachy_mini_conversation_app.tools.azure_devops_create_pr import AzureDevOpsCreatePR


class FakeResponse:
    """Minimal httpx-compatible response stub for tool tests."""

    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        """Store the payload and HTTP status for later assertions."""
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.request = httpx.Request("POST", "https://example.test")

    def raise_for_status(self) -> None:
        """Raise an HTTPStatusError when the configured status is not successful."""
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request, text=self.text)
            raise httpx.HTTPStatusError("request failed", request=self.request, response=response)

    def json(self) -> dict[str, object]:
        """Return the stored JSON payload."""
        return self._payload


@pytest.mark.asyncio
async def test_azure_devops_create_pr_creates_pull_request_with_reviewers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tool should create a pull request and resolve reviewer emails."""
    calls: list[tuple[str, str, dict[str, object]]] = []

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
            return False

        def get(self, url: str, params: dict[str, object]) -> FakeResponse:
            calls.append(("get", url, params))
            return FakeResponse({"value": [{"id": "reviewer-guid"}]})

        def post(self, url: str, params: dict[str, object], json: dict[str, object]) -> FakeResponse:
            calls.append(("post", url, {"params": params, "json": json}))
            return FakeResponse(
                {
                    "pullRequestId": 42,
                    "remoteUrl": "https://dev.azure.com/example/project/_git/repo/pullrequest/42",
                }
            )

    monkeypatch.setenv("AZURE_DEVOPS_PAT", "test-pat")
    monkeypatch.setenv("AZURE_DEVOPS_ORG", "example-org")
    monkeypatch.setattr("reachy_mini_conversation_app.tools.azure_devops_create_pr.httpx.Client", FakeClient)

    deps = ToolDependencies(reachy_mini=MagicMock(), movement_manager=MagicMock())

    result = await AzureDevOpsCreatePR()(
        deps,
        organization="example-org",
        project="project-name",
        repo_name="repo-name",
        source_branch="feature/tooling",
        title="Add Azure DevOps PR tool",
        description="Implements Azure DevOps PR creation support.",
        reviewers=["reviewer@example.com"],
    )

    assert result == {
        "status": "pr_created",
        "pr_id": 42,
        "url": "https://dev.azure.com/example/project/_git/repo/pullrequest/42",
    }
    assert calls[0] == (
        "get",
        "https://vssps.dev.azure.com/example-org/_apis/identities",
        {
            "searchFilter": "General",
            "filterValue": "reviewer@example.com",
            "queryMembership": "None",
            "api-version": "7.1-preview.1",
        },
    )
    assert calls[1] == (
        "post",
        "https://dev.azure.com/example-org/project-name/_apis/git/repositories/repo-name/pullrequests",
        {
            "params": {"api-version": "7.2-preview.2"},
            "json": {
                "sourceRefName": "refs/heads/feature/tooling",
                "targetRefName": "refs/heads/development",
                "title": "Add Azure DevOps PR tool",
                "description": "Implements Azure DevOps PR creation support.",
                "reviewers": [{"id": "reviewer-guid", "uniqueName": "reviewer@example.com"}],
            },
        },
    )


@pytest.mark.asyncio
async def test_azure_devops_create_pr_requires_pat(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool should fail gracefully when the PAT is missing."""
    monkeypatch.delenv("AZURE_DEVOPS_PAT", raising=False)
    monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)

    deps = ToolDependencies(reachy_mini=MagicMock(), movement_manager=MagicMock())

    result = await AzureDevOpsCreatePR()(
        deps,
        organization="example-org",
        project="project-name",
        repo_name="repo-name",
        source_branch="feature/tooling",
        title="Add Azure DevOps PR tool",
        description="Implements Azure DevOps PR creation support.",
    )

    assert result == {"error": "AZURE_DEVOPS_PAT is not configured"}
