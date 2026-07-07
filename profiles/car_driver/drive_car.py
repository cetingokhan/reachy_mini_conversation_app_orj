import logging
from typing import Any, Dict, Literal

from reachy_mini_conversation_app import car_state
from reachy_mini_conversation_app.car_ble import CarBleConnectionError, car_ble_client
from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

Action = Literal[
    "forward",
    "back",
    "stop",
    "center",
    "left1",
    "left2",
    "right1",
    "right2",
    "turn_left1",
    "turn_left2",
    "turn_right1",
    "turn_right2",
]
ACTIONS: tuple[Action, ...] = (
    "forward",
    "back",
    "stop",
    "center",
    "left1",
    "left2",
    "right1",
    "right2",
    "turn_left1",
    "turn_left2",
    "turn_right1",
    "turn_right2",
)
# Actions that drive the car (as opposed to just stopping/centering the wheels), so they count
# toward the blind-driving safety cap and need a distance/duration.
DRIVING_ACTIONS = {"forward", "back", "turn_left1", "turn_left2", "turn_right1", "turn_right2"}
STEERING_ACTIONS = {"center", "left1", "left2", "right1", "right2"}
TURN_TO_STEERING = {
    "turn_left1": "left1",
    "turn_left2": "left2",
    "turn_right1": "right1",
    "turn_right2": "right2",
}

Distance = Literal["short", "medium", "long"]
DISTANCE_MS = {"short": 500, "medium": 1000, "long": 2000}
_steering_state = "center"


class DriveCar(Tool):
    """Drive the LEGO SPIKE car chassis over BLE."""

    name = "drive_car"
    description = (
        "Drive the LEGO SPIKE car chassis you are mounted on. 'forward'/'back' move one step in that distance "
        "and stop automatically; 'stop' cancels the current step early; 'center' straightens the wheels; "
        "'left1'/'left2'/'right1'/'right2' only set steering angle without driving; "
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
                "description": (
                    "Use left1/left2/right1/right2 to steer first, then call forward/back. "
                    "Use turn_* only when you need steering+forward arc in one step."
                ),
            },
            "distance": {
                "type": "string",
                "enum": list(DISTANCE_MS),
                "description": (
                    "How far this driving/turning step should go. Ignored for stop/center/left*/right*."
                ),
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

        global _steering_state
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
        if action in STEERING_ACTIONS:
            _steering_state = action
        elif action in TURN_TO_STEERING:
            _steering_state = TURN_TO_STEERING[action]

        logger.info("Tool call: drive_car action=%s distance=%s", action, distance)

        try:
            just_connected = await car_ble_client.send_command(command)
        except CarBleConnectionError as e:
            logger.exception("drive_car failed to connect")
            return {"error": f"Could not connect to the car hub: {e}"}
        except Exception as e:
            logger.exception("drive_car failed")
            return {"error": f"drive_car failed: {type(e).__name__}: {e}"}

        result: Dict[str, Any] = {
            "status": action,
            "distance": distance,
            "just_connected": just_connected,
            "steering_state": _steering_state,
        }
        if just_connected:
            result["message"] = "Just connected to the car over Bluetooth."
        return result
