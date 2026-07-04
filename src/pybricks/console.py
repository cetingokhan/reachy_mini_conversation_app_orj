"""Local BLE console to drive the LEGO SPIKE car running carhub.py.

Usage:
    python console.py [hub-name]

Type commands and press Enter. Same command set as carhub.py:
forward, back, stop, center, turn_left1, turn_left2, turn_right1, turn_right2, quit
Append a duration in ms to scale the step, e.g. "forward 1500".
"""

import os
import sys
import asyncio

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from pybricksdev.ble.pybricks import PYBRICKS_SERVICE_UUID
from pybricksdev.connections.pybricks import PybricksHubBLE


CARHUB_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "reachy_mini_conversation_app", "car_hub_program.py")
# ponytail: set to your hub's advertised name, or pass it as a CLI argument
DEFAULT_HUB_NAME = "Pybricks Hub"

COMMANDS = ["forward", "back", "stop", "center", "turn_left1", "turn_left2", "turn_right1", "turn_right2", "quit"]


async def find_hub_device(hub_name: str, timeout: float = 10.0) -> BLEDevice:
    """Scan for a Pybricks-advertising device.

    pybricksdev's own ``find_device`` requires a local name in the advertisement, but this hub
    only reveals its name via GATT after connecting, so that helper always times out. Match on
    the Pybricks service UUID instead, and only enforce hub_name when a name is already cached.
    """

    def _matches(d: BLEDevice, adv: AdvertisementData) -> bool:
        if PYBRICKS_SERVICE_UUID not in adv.service_uuids:
            return False
        return d.name is None or d.name == hub_name

    device = await BleakScanner.find_device_by_filter(_matches, timeout=timeout)
    if device is None:
        raise TimeoutError(f"No car hub found over BLE (name={hub_name!r})")
    return device


async def run_console(hub_name: str) -> None:
    """Connect to the hub over BLE, upload/start carhub.py, then relay typed commands."""
    print(f"Scanning for hub '{hub_name}'...")
    device = await find_hub_device(hub_name)
    hub = PybricksHubBLE(device)

    print("Connecting...")
    await hub.connect()
    try:
        print("Uploading and starting carhub.py...")
        await hub.run(CARHUB_SCRIPT, wait=False, print_output=True)

        print("Connected. Commands: " + ", ".join(COMMANDS))
        while True:
            command = (await asyncio.to_thread(input, "> ")).strip()
            if not command:
                continue
            if command not in COMMANDS and command.split()[0] not in COMMANDS:
                print(f"unknown command: {command}")
                continue
            await hub.write_line(command)
            if command == "quit":
                break
    finally:
        await hub.disconnect()


def main() -> None:
    """Parse the optional hub-name CLI argument and run the console."""
    hub_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HUB_NAME
    asyncio.run(run_console(hub_name))


if __name__ == "__main__":
    main()
