"""Tests for the persistent BLE client to the LEGO car hub."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reachy_mini_conversation_app.car_ble import CarBleClient, CarBleConnectionError


def _fake_device() -> MagicMock:
    device = MagicMock()
    device.name = "Pybricks Hub"
    return device


@pytest.mark.asyncio
async def test_ensure_connected_reuses_existing_connection() -> None:
    """A second call should not scan/connect again while still connected."""
    client = CarBleClient()

    with (
        patch("reachy_mini_conversation_app.car_ble.BleakScanner.find_device_by_filter", new=AsyncMock()) as find_mock,
        patch("reachy_mini_conversation_app.car_ble.BleakClient") as client_cls,
    ):
        find_mock.return_value = _fake_device()
        ble_client = client_cls.return_value
        ble_client.is_connected = True
        ble_client.connect = AsyncMock()

        just_connected_1 = await client.ensure_connected()
        just_connected_2 = await client.ensure_connected()

        assert just_connected_1 is True
        assert just_connected_2 is False
        find_mock.assert_awaited_once()
        ble_client.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_connected_reconnects_after_disconnect() -> None:
    """A dropped connection should trigger a fresh scan/connect on the next call."""
    client = CarBleClient()

    with (
        patch("reachy_mini_conversation_app.car_ble.BleakScanner.find_device_by_filter", new=AsyncMock()) as find_mock,
        patch("reachy_mini_conversation_app.car_ble.BleakClient") as client_cls,
    ):
        find_mock.return_value = _fake_device()
        ble_client = client_cls.return_value
        ble_client.is_connected = True
        ble_client.connect = AsyncMock()

        await client.ensure_connected()
        client._handle_disconnect(ble_client)  # simulate the hub going out of range

        just_connected = await client.ensure_connected()

        assert just_connected is True
        assert find_mock.await_count == 2


@pytest.mark.asyncio
async def test_ensure_connected_raises_when_hub_not_found() -> None:
    """No matching BLE device should raise a clear connection error."""
    client = CarBleClient()

    with patch(
        "reachy_mini_conversation_app.car_ble.BleakScanner.find_device_by_filter", new=AsyncMock()
    ) as find_mock:
        find_mock.return_value = None

        with pytest.raises(CarBleConnectionError):
            await client.ensure_connected()


@pytest.mark.asyncio
async def test_send_command_writes_stdin_payload() -> None:
    """send_command should write the WRITE_STDIN-prefixed, newline-terminated command."""
    client = CarBleClient()

    with (
        patch("reachy_mini_conversation_app.car_ble.BleakScanner.find_device_by_filter", new=AsyncMock()) as find_mock,
        patch("reachy_mini_conversation_app.car_ble.BleakClient") as client_cls,
    ):
        find_mock.return_value = _fake_device()
        ble_client = client_cls.return_value
        ble_client.is_connected = True
        ble_client.connect = AsyncMock()
        ble_client.write_gatt_char = AsyncMock()

        await client.send_command("forward")

        ble_client.write_gatt_char.assert_awaited_once()
        args, kwargs = ble_client.write_gatt_char.await_args
        assert args[1] == b"\x06forward\n"
