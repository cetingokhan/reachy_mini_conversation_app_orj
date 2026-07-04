import logging
from typing import Any, Dict, Literal

from reachy_mini_conversation_app import car_state
from reachy_mini_conversation_app.car_ble import CarBleConnectionError, car_ble_client
from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

Action = Literal["forward", "back", "stop", "center", "turn_left1", "turn_left2", "turn_right1", "turn_right2"]
ACTIONS: tuple[Action, ...] = (
    "forward",
    "back",
    "stop",
    "center",
    "turn_left1",
    "turn_left2",
    "turn_right1",
    "turn_right2",
)
# Actions that drive the car (as opposed to just stopping/centering the wheels), so they count
# toward the blind-driving safety cap and need a distance/duration.
DRIVING_ACTIONS = {"forward", "back", "turn_left1", "turn_left2", "turn_right1", "turn_right2"}

Distance = Literal["short", "medium", "long"]
DISTANCE_MS = {"short": 500, "medium": 1000, "long": 2000}


class DriveCar(Tool):
    """Drive the LEGO SPIKE car chassis over BLE."""

    name = "drive_car"
    description = (
        "Drive the LEGO SPIKE car chassis you are mounted on. 'forward'/'back' move one step in that distance "
        "and stop automatically; 'stop' cancels the current step early; 'center' straightens the wheels; "
        "'turn_left1'/'turn_left2'/'turn_right1'/'turn_right2' steer to a preset angle (1=slight, 2=sharp) AND "
        "drive forward at the same time, so the chassis actually arcs instead of just wagging the front wheel. "
        "Use 'distance' to scale how far a driving/turning step goes: 'short' for fine adjustments close to a "
        "target, 'long' when the target is far away. You may need to call this repeatedly, rechecking the "
        f"camera every {car_state.MAX_BLIND_STEPS} steps, to actually reach a distant goal."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(ACTIONS),
            },
            "distance": {
                "type": "string",
                "enum": list(DISTANCE_MS),
                "description": "How far this driving/turning step should go. Ignored for 'stop'/'center'.",
            },
        },
        "required": ["action"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        """Send one drive/steer command to the car hub over BLE."""
        action = kwargs.get("action")
        if action not in ACTIONS:
            return {"error": f"action must be one of {ACTIONS}"}

        distance = kwargs.get("distance") or "medium"
        if distance not in DISTANCE_MS:
            return {"error": f"distance must be one of {tuple(DISTANCE_MS)}"}

        command = action
        if action in DRIVING_ACTIONS:
            blind_steps = car_state.record_drive_step()
            if blind_steps > car_state.MAX_BLIND_STEPS:
                return {
                    "error": (
                        f"Driven {car_state.MAX_BLIND_STEPS} steps in a row without a camera check. Call the "
                        "camera tool to look before continuing to move."
                    )
                }
            command = f"{action} {DISTANCE_MS[distance]}"

        logger.info("Tool call: drive_car action=%s distance=%s", action, distance)

        try:
            just_connected = await car_ble_client.send_command(command)
        except CarBleConnectionError as e:
            logger.error("drive_car failed to connect: %s", e)
            return {"error": f"Could not connect to the car hub: {e}"}
        except Exception as e:
            logger.error("drive_car failed: %s", e)
            return {"error": f"drive_car failed: {type(e).__name__}: {e}"}

        result: Dict[str, Any] = {"status": action, "distance": distance, "just_connected": just_connected}
        if just_connected:
            result["message"] = "Just connected to the car over Bluetooth."
        return result
