"""Self-check for car_hub_program.py's command dispatch, no hub/BLE required."""

import os
import importlib.util


_SPEC = importlib.util.spec_from_file_location(
    "car_hub_program",
    os.path.join(os.path.dirname(__file__), "..", "reachy_mini_conversation_app", "car_hub_program.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
carhub = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(carhub)


def demo():
    """Assert dispatch handles every known command and rejects unknown ones."""
    assert carhub.dispatch("forward") == "ok forward"
    assert carhub.dispatch("back") == "ok back"
    assert carhub.dispatch("stop") == "ok stop"
    for preset in carhub.STEERING_ANGLES:
        assert carhub.dispatch(preset) == "ok " + preset
    assert carhub.dispatch("sideways").startswith("err")


if __name__ == "__main__":
    demo()
    print("carhub dispatch self-check passed")
