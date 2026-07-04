"""Persistent BLE client for the LEGO SPIKE car chassis running pybricks' carhub.py.

Talks directly to the Pybricks BLE GATT service (constants below), so the app only
depends on ``bleak`` instead of the full ``pybricksdev`` toolchain. The hub is expected
to already be running its user program (started on the hub itself); this client only
connects and writes lines to its stdin.
"""

import asyncio
import logging

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from reachy_mini_conversation_app.config import config


logger = logging.getLogger(__name__)

# Pybricks BLE profile: https://github.com/pybricks/technical-info/blob/master/pybricks-ble-profile.md
PYBRICKS_SERVICE_UUID = "c5f50001-8280-46da-89f4-6d8051e4aeef"
PYBRICKS_COMMAND_EVENT_UUID = "c5f50002-8280-46da-89f4-6d8051e4aeef"
WRITE_STDIN_COMMAND = 0x06

BLE_SCAN_TIMEOUT_S = 10.0


class CarBleConnectionError(RuntimeError):
    """Raised when the car hub cannot be found or connected to over BLE."""


class CarBleClient:
    """Keeps a single BLE connection to the car hub alive across tool calls."""

    def __init__(self) -> None:
        """Set up the client with no active connection."""
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()

    def _handle_disconnect(self, _: BleakClient) -> None:
        logger.warning("Car hub BLE connection dropped, will reconnect on next command")
        self._client = None

    async def ensure_connected(self) -> bool:
        """Connect to the car hub if not already connected. Returns True if a fresh connection was made."""
        async with self._lock:
            if self._client is not None and self._client.is_connected:
                return False

            hub_name = config.LEGO_CAR_HUB_NAME
            logger.info("Scanning for car hub%s...", f" '{hub_name}'" if hub_name else "")
            device: BLEDevice | None = await BleakScanner.find_device_by_filter(
                lambda d, adv: PYBRICKS_SERVICE_UUID in adv.service_uuids and (hub_name is None or d.name == hub_name),
                timeout=BLE_SCAN_TIMEOUT_S,
            )
            if device is None:
                raise CarBleConnectionError(f"No car hub found over BLE (name={hub_name!r})")

            client = BleakClient(device, disconnected_callback=self._handle_disconnect)
            await client.connect()
            self._client = client
            logger.info("Connected to car hub %s", device.name)
            return True

    async def send_command(self, command: str) -> bool:
        """Ensure connection and write one command line to the hub's stdin. Returns just_connected."""
        just_connected = await self.ensure_connected()
        assert self._client is not None  # ensure_connected raises if it can't set this
        # ponytail: commands are short fixed keywords that always fit in one BLE ATT write;
        # add chunking (like pybricksdev's write_string) if longer commands are ever needed.
        payload = bytes([WRITE_STDIN_COMMAND]) + (command + "\n").encode()
        await self._client.write_gatt_char(PYBRICKS_COMMAND_EVENT_UUID, payload, response=True)
        return just_connected

    async def disconnect(self) -> None:
        """Disconnect from the car hub, if connected."""
        if self._client is not None and self._client.is_connected:
            await self._client.disconnect()
        self._client = None


car_ble_client = CarBleClient()
