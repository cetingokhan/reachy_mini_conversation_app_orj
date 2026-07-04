"""Tests for the car_driver profile's drive_car tool."""

import sys
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reachy_mini_conversation_app.car_ble import CarBleConnectionError
from reachy_mini_conversation_app.tools.core_tools import ToolDependencies


def _load_drive_car():
    """Import the profile-local drive_car.py module (not on the normal import path)."""
    module_path = Path(__file__).parents[2] / "profiles" / "car_driver" / "drive_car.py"
    spec = importlib.util.spec_from_file_location("drive_car_under_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


drive_car_module = _load_drive_car()


@pytest.fixture
def deps() -> ToolDependencies:
    """Bare tool dependencies; drive_car does not use reachy_mini or movement_manager."""
    return ToolDependencies(reachy_mini=MagicMock(), movement_manager=MagicMock())


@pytest.mark.asyncio
async def test_drive_car_rejects_unknown_action(deps: ToolDependencies) -> None:
    """An action outside the fixed command set is rejected before touching BLE."""
    result = await drive_car_module.DriveCar()(deps, action="sideways")

    assert "error" in result


@pytest.mark.asyncio
async def test_drive_car_sends_command_and_reports_connection(deps: ToolDependencies) -> None:
    """A successful call forwards the action and reports whether it just connected."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=True)) as send_mock:
        result = await drive_car_module.DriveCar()(deps, action="forward")

    send_mock.assert_awaited_once_with("forward")
    assert result["status"] == "forward"
    assert result["just_connected"] is True
    assert "message" in result


@pytest.mark.asyncio
async def test_drive_car_reports_connection_error(deps: ToolDependencies) -> None:
    """A BLE connection failure is returned as an error, not raised."""
    with patch.object(
        drive_car_module.car_ble_client,
        "send_command",
        new=AsyncMock(side_effect=CarBleConnectionError("no hub found")),
    ):
        result = await drive_car_module.DriveCar()(deps, action="left1")

    assert "error" in result
