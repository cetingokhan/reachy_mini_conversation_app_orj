"""Self-check for carhub.py's command dispatch, no hub/BLE required."""

import carhub


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
