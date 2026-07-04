import logging
from typing import Any, Dict, Literal

from reachy_mini_conversation_app.car_ble import CarBleConnectionError, car_ble_client
from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

Action = Literal["forward", "back", "stop", "left1", "left2", "right1", "right2", "center"]
ACTIONS: tuple[Action, ...] = ("forward", "back", "stop", "left1", "left2", "right1", "right2", "center")


class DriveCar(Tool):
    """Drive the LEGO SPIKE car chassis over BLE."""

    name = "drive_car"
    description = (
        "Drive the LEGO SPIKE car chassis you are mounted on. 'forward'/'back' move one step and stop "
        "automatically; 'stop' cancels the current step early; 'left1'/'left2'/'right1'/'right2' steer to a "
        "preset angle (1=slight, 2=sharp); 'center' straightens the wheels."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(ACTIONS),
            },
        },
        "required": ["action"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        """Send one drive/steer command to the car hub over BLE."""
        action = kwargs.get("action")
        if action not in ACTIONS:
            return {"error": f"action must be one of {ACTIONS}"}

        logger.info("Tool call: drive_car action=%s", action)

        try:
            just_connected = await car_ble_client.send_command(action)
        except CarBleConnectionError as e:
            logger.error("drive_car failed to connect: %s", e)
            return {"error": f"Could not connect to the car hub: {e}"}
        except Exception as e:
            logger.error("drive_car failed: %s", e)
            return {"error": f"drive_car failed: {type(e).__name__}: {e}"}

        result: Dict[str, Any] = {"status": action, "just_connected": just_connected}
        if just_connected:
            result["message"] = "Just connected to the car over Bluetooth."
        return result
