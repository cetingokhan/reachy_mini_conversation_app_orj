"""Local BLE console to drive the LEGO SPIKE car running carhub.py.

Usage:
    python console.py [hub-name]

Type commands and press Enter. Same command set as carhub.py:
forward, back, stop, center, left1, left2, right1, right2, quit
"""

import os
import sys
import asyncio

from pybricksdev.ble import find_device
from pybricksdev.connections.pybricks import PybricksHubBLE


CARHUB_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "reachy_mini_conversation_app", "car_hub_program.py")
# ponytail: set to your hub's advertised name, or pass it as a CLI argument
DEFAULT_HUB_NAME = "Pybricks Hub"

COMMANDS = ["forward", "back", "stop", "center", "left1", "left2", "right1", "right2", "quit"]


async def run_console(hub_name: str) -> None:
    """Connect to the hub over BLE, upload/start carhub.py, then relay typed commands."""
    print(f"Scanning for hub '{hub_name}'...")
    device = await find_device(hub_name, timeout=10.0)
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
            if command not in COMMANDS:
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
