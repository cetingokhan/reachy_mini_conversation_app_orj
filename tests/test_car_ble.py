"""Tests for the persistent BLE client to the LEGO car hub."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pybricksdev.connections import ConnectionState

from reachy_mini_conversation_app.car_ble import CarBleClient, CarBleConnectionError


def _fake_hub() -> MagicMock:
    hub = MagicMock()
    hub.connect = AsyncMock()
    hub.run = AsyncMock()
    hub.write_line = AsyncMock()
    hub.disconnect = AsyncMock()
    hub.connection_state_observable.value = ConnectionState.CONNECTED
    return hub


@pytest.mark.asyncio
async def test_ensure_connected_reuses_existing_connection() -> None:
    """A second call should not scan/connect again while still connected."""
    client = CarBleClient()

    with (
        patch("reachy_mini_conversation_app.car_ble.find_device", new=AsyncMock()) as find_mock,
        patch("reachy_mini_conversation_app.car_ble.PybricksHubBLE") as hub_cls,
    ):
        find_mock.return_value = MagicMock()
        hub = _fake_hub()
        hub_cls.return_value = hub

        just_connected_1 = await client.ensure_connected()
        just_connected_2 = await client.ensure_connected()

        assert just_connected_1 is True
        assert just_connected_2 is False
        find_mock.assert_awaited_once()
        hub.connect.assert_awaited_once()
        hub.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_connected_reconnects_after_disconnect() -> None:
    """A dropped connection should trigger a fresh scan/connect on the next call."""
    client = CarBleClient()

    with (
        patch("reachy_mini_conversation_app.car_ble.find_device", new=AsyncMock()) as find_mock,
        patch("reachy_mini_conversation_app.car_ble.PybricksHubBLE") as hub_cls,
    ):
        find_mock.return_value = MagicMock()
        hub = _fake_hub()
        hub_cls.return_value = hub

        await client.ensure_connected()
        hub.connection_state_observable.value = ConnectionState.DISCONNECTED  # hub went out of range

        just_connected = await client.ensure_connected()

        assert just_connected is True
        assert find_mock.await_count == 2


@pytest.mark.asyncio
async def test_ensure_connected_raises_when_hub_not_found() -> None:
    """No matching BLE device should raise a clear connection error."""
    client = CarBleClient()

    with patch("reachy_mini_conversation_app.car_ble.find_device", new=AsyncMock()) as find_mock:
        find_mock.side_effect = TimeoutError

        with pytest.raises(CarBleConnectionError):
            await client.ensure_connected()


@pytest.mark.asyncio
async def test_send_command_writes_stdin_line() -> None:
    """send_command should write the command as a line to the hub's stdin."""
    client = CarBleClient()

    with (
        patch("reachy_mini_conversation_app.car_ble.find_device", new=AsyncMock()) as find_mock,
        patch("reachy_mini_conversation_app.car_ble.PybricksHubBLE") as hub_cls,
    ):
        find_mock.return_value = MagicMock()
        hub = _fake_hub()
        hub_cls.return_value = hub

        await client.send_command("forward")

        hub.write_line.assert_awaited_once_with("forward")


@pytest.mark.asyncio
async def test_ensure_connected_uploads_and_starts_car_hub_program() -> None:
    """Connecting should upload and start car_hub_program.py without waiting for it to finish."""
    client = CarBleClient()

    with (
        patch("reachy_mini_conversation_app.car_ble.find_device", new=AsyncMock()) as find_mock,
        patch("reachy_mini_conversation_app.car_ble.PybricksHubBLE") as hub_cls,
    ):
        find_mock.return_value = MagicMock()
        hub = _fake_hub()
        hub_cls.return_value = hub

        await client.ensure_connected()

        args, kwargs = hub.run.await_args
        assert args[0].endswith("car_hub_program.py")
        assert kwargs["wait"] is False
