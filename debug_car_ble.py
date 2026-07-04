"""Standalone BLE diagnostic for the LEGO car hub connection.

Run with the main app's venv active: ``uv run python debug_car_ble.py``.
Connects, uploads+starts car_hub_program.py (print_output=True echoes the hub's
stdout below), and sends a forward/stop round-trip so you can check the car moved.

ponytail: throwaway script, delete once the connection is confirmed working end-to-end.
"""

import asyncio
import logging

from reachy_mini_conversation_app.config import config
from reachy_mini_conversation_app.car_ble import car_ble_client


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    """Connect, run the hub program, send a forward/stop round-trip, and report the result."""
    print(f"Configured LEGO_CAR_HUB_NAME={config.LEGO_CAR_HUB_NAME!r}")
    just_connected = await car_ble_client.send_command("forward")
    print(f"just_connected={just_connected}")

    await asyncio.sleep(1.0)
    await car_ble_client.send_command("stop")
    print("Sent forward -> stop. Did the car actually move?")

    await car_ble_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
