"""Persistent BLE client for the LEGO SPIKE car chassis.

Uses pybricksdev (the same approach as src/pybricks/console.py) so connecting
also compiles, uploads, and starts car_hub_program.py on the hub -- the hub
just needs to be powered on, no manual "run program" step required there.
"""

import asyncio
import logging
from pathlib import Path

from pybricksdev.ble import find_device
from pybricksdev.connections import ConnectionState
from pybricksdev.connections.pybricks import PybricksHubBLE

from reachy_mini_conversation_app.config import config


logger = logging.getLogger(__name__)

CAR_HUB_PROGRAM = Path(__file__).with_name("car_hub_program.py")
BLE_SCAN_TIMEOUT_S = 10.0


class CarBleConnectionError(RuntimeError):
    """Raised when the car hub cannot be found, connected to, or started over BLE."""


class CarBleClient:
    """Keeps a single BLE connection to the car hub alive across tool calls, running its program on connect."""

    def __init__(self) -> None:
        """Set up the client with no active connection."""
        self._hub: PybricksHubBLE | None = None
        self._lock = asyncio.Lock()

    def _is_connected(self) -> bool:
        return self._hub is not None and self._hub.connection_state_observable.value == ConnectionState.CONNECTED

    async def ensure_connected(self) -> bool:
        """Connect to the car hub and start its program if not already connected. Returns True if freshly connected."""
        async with self._lock:
            if self._is_connected():
                return False

            hub_name = config.LEGO_CAR_HUB_NAME
            logger.info("Scanning for car hub%s...", f" '{hub_name}'" if hub_name else "")
            try:
                device = await find_device(hub_name, timeout=BLE_SCAN_TIMEOUT_S)
            except asyncio.TimeoutError as exc:
                raise CarBleConnectionError(f"No car hub found over BLE (name={hub_name!r})") from exc

            hub = PybricksHubBLE(device)
            await hub.connect()
            logger.info("Connected to car hub, uploading and starting car_hub_program.py...")
            await hub.run(str(CAR_HUB_PROGRAM), wait=False, print_output=True)
            self._hub = hub
            logger.info("Car hub program running")
            return True

    async def send_command(self, command: str) -> bool:
        """Ensure connection and write one command line to the hub's stdin. Returns just_connected."""
        just_connected = await self.ensure_connected()
        assert self._hub is not None  # ensure_connected raises if it can't set this
        await self._hub.write_line(command)
        return just_connected

    async def disconnect(self) -> None:
        """Disconnect from the car hub, if connected."""
        if self._hub is not None:
            await self._hub.disconnect()
        self._hub = None


car_ble_client = CarBleClient()
