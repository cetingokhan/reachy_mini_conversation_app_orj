"""Tests for configuration helpers."""

import pytest

from reachy_mini_conversation_app import config


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("45", 45.0),
        ("", config.DEFAULT_APP_TIMEOUT_MINUTES),  # unset/blank falls back to the default
        ("soon", config.DEFAULT_APP_TIMEOUT_MINUTES),  # unparseable falls back to the default
        ("0", None),  # non-positive disables the watchdog
        ("-1", None),
    ],
)
def test_resolve_app_timeout_minutes(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: float | None,
) -> None:
    """The env timeout parses to minutes, falls back to the default, or disables on non-positive."""
    monkeypatch.setenv(config.APP_TIMEOUT_MINUTES_ENV, raw_value)

    assert config.resolve_app_timeout_minutes() == expected


def test_refresh_runtime_config_from_env_loads_azure_devops_auth(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Refreshing config should expose Azure DevOps auth values without warning when set."""
    monkeypatch.setenv(config.AZURE_DEVOPS_ORG_ENV, "demo-org")
    monkeypatch.setenv(config.AZURE_DEVOPS_PAT_ENV, "demo-pat")
    monkeypatch.setenv(config.GITHUB_COPILOT_CLI_TOKEN_ENV, "demo-cli-token")

    with caplog.at_level("WARNING"):
        config.refresh_runtime_config_from_env()

    assert config.config.AZURE_DEVOPS_ORG == "demo-org"
    assert config.config.AZURE_DEVOPS_PAT == "demo-pat"
    assert config.config.GITHUB_COPILOT_CLI_TOKEN == "demo-cli-token"
    assert "Missing AZURE_DEVOPS_PAT" not in caplog.text
    assert "Missing GITHUB_COPILOT_CLI_TOKEN" not in caplog.text


def test_refresh_runtime_config_from_env_warns_for_missing_optional_auth(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Refreshing config should warn when optional auth tokens are missing."""
    monkeypatch.delenv(config.AZURE_DEVOPS_PAT_ENV, raising=False)
    monkeypatch.delenv(config.GITHUB_COPILOT_CLI_TOKEN_ENV, raising=False)

    with caplog.at_level("WARNING"):
        config.refresh_runtime_config_from_env()

    assert config.config.AZURE_DEVOPS_PAT is None
    assert config.config.GITHUB_COPILOT_CLI_TOKEN is None
    assert "Missing AZURE_DEVOPS_PAT" in caplog.text
    assert "Missing GITHUB_COPILOT_CLI_TOKEN" in caplog.text
