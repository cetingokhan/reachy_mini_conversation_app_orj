"""Tests for the car_driver profile's drive_car tool."""

import sys
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reachy_mini_conversation_app import car_state
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


@pytest.fixture(autouse=True)
def reset_blind_step_counter():
    """Reset the module-level blind-step safety counter so tests stay isolated."""
    car_state.reset_after_camera_check()
    yield
    car_state.reset_after_camera_check()


@pytest.mark.asyncio
async def test_drive_car_rejects_unknown_action(deps: ToolDependencies) -> None:
    """An action outside the fixed command set is rejected before touching BLE."""
    result = await drive_car_module.DriveCar()(deps, action="sideways")

    assert "error" in result


@pytest.mark.asyncio
async def test_drive_car_rejects_unknown_distance(deps: ToolDependencies) -> None:
    """A distance outside the fixed enum is rejected before touching BLE."""
    result = await drive_car_module.DriveCar()(deps, action="forward", distance="far away")

    assert "error" in result


@pytest.mark.asyncio
async def test_drive_car_sends_command_and_reports_connection(deps: ToolDependencies) -> None:
    """A successful call forwards the action+duration and reports whether it just connected."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=True)) as send_mock:
        result = await drive_car_module.DriveCar()(deps, action="forward")

    send_mock.assert_awaited_once_with("forward 1000")
    assert result["status"] == "forward"
    assert result["just_connected"] is True
    assert "message" in result


@pytest.mark.asyncio
async def test_drive_car_uses_distance_to_scale_duration(deps: ToolDependencies) -> None:
    """The 'distance' parameter maps to a longer/shorter duration sent to the hub."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=False)) as send_mock:
        await drive_car_module.DriveCar()(deps, action="turn_left1", distance="long")

    send_mock.assert_awaited_once_with("turn_left1 2000")


@pytest.mark.asyncio
async def test_drive_car_steer_only_action_has_no_duration(deps: ToolDependencies) -> None:
    """Steer-only actions should send a raw steering command with no drive duration."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=False)) as send_mock:
        result = await drive_car_module.DriveCar()(deps, action="right2", distance="long")

    send_mock.assert_awaited_once_with("right2")
    assert result["steering_state"] == "right2"


@pytest.mark.asyncio
async def test_drive_car_stop_and_center_ignore_distance(deps: ToolDependencies) -> None:
    """'stop'/'center' don't drive, so no duration is appended and they don't count toward the safety cap."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=False)) as send_mock:
        await drive_car_module.DriveCar()(deps, action="stop", distance="long")
        await drive_car_module.DriveCar()(deps, action="center")

    assert send_mock.await_args_list[0].args == ("stop",)
    assert send_mock.await_args_list[1].args == ("center",)


@pytest.mark.asyncio
async def test_drive_car_reports_connection_error(deps: ToolDependencies) -> None:
    """A BLE connection failure is returned as an error, not raised."""
    with patch.object(
        drive_car_module.car_ble_client,
        "send_command",
        new=AsyncMock(side_effect=CarBleConnectionError("no hub found")),
    ):
        result = await drive_car_module.DriveCar()(deps, action="turn_left1")

    assert "error" in result


@pytest.mark.asyncio
async def test_drive_car_blocks_after_too_many_blind_steps(deps: ToolDependencies) -> None:
    """Driving/turning repeatedly without a camera check is refused past the safety cap."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=False)) as send_mock:
        for _ in range(car_state.MAX_BLIND_STEPS):
            result = await drive_car_module.DriveCar()(deps, action="forward")
            assert "error" not in result

        blocked = await drive_car_module.DriveCar()(deps, action="forward")

    assert "error" in blocked
    assert send_mock.await_count == car_state.MAX_BLIND_STEPS


@pytest.mark.asyncio
async def test_drive_car_camera_check_resets_blind_step_counter(deps: ToolDependencies) -> None:
    """Calling the camera tool clears the counter so driving can resume."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=False)):
        for _ in range(car_state.MAX_BLIND_STEPS):
            await drive_car_module.DriveCar()(deps, action="forward")

        car_state.reset_after_camera_check()
        result = await drive_car_module.DriveCar()(deps, action="forward")

    assert "error" not in result


@pytest.mark.asyncio
async def test_drive_car_steer_only_does_not_consume_blind_step_budget(deps: ToolDependencies) -> None:
    """Steering commands should not count as blind driving steps."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=False)):
        for _ in range(20):
            result = await drive_car_module.DriveCar()(deps, action="left1")
            assert "error" not in result

        for _ in range(car_state.MAX_BLIND_STEPS):
            result = await drive_car_module.DriveCar()(deps, action="forward")
            assert "error" not in result

        blocked = await drive_car_module.DriveCar()(deps, action="forward")

    assert "error" in blocked


@pytest.mark.asyncio
async def test_drive_car_reports_steering_state_after_turn_action(deps: ToolDependencies) -> None:
    """Turn-and-drive actions should report the steering preset they imply."""
    with patch.object(drive_car_module.car_ble_client, "send_command", new=AsyncMock(return_value=False)):
        result = await drive_car_module.DriveCar()(deps, action="turn_right1")

    assert result["steering_state"] == "right1"
