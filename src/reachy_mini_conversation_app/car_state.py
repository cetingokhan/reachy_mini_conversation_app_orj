"""Shared safety counter limiting blind car driving between camera checks."""

MAX_BLIND_STEPS = 4

_blind_steps = 0


def record_drive_step() -> int:
    """Record one drive/turn step taken without a camera check, returning the new count."""
    global _blind_steps
    _blind_steps += 1
    return _blind_steps


def reset_after_camera_check() -> None:
    """Reset the blind-step count after a successful camera check."""
    global _blind_steps
    _blind_steps = 0
