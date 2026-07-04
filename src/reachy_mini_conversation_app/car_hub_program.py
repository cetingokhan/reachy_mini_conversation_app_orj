from usys import stdin

from pybricks.hubs import PrimeHub
from pybricks.parameters import Port, Direction
from pybricks.pupdevices import Motor


hub = PrimeHub()
# ponytail: motors are mirrored on the chassis, so B is flipped to make positive
# speed on both mean "forward" instead of spinning opposite ways
motor_back_right = Motor(Port.B, Direction.COUNTERCLOCKWISE)
motor_back_left = Motor(Port.A)
motor_front_steering_wheel = Motor(Port.C)

# ponytail: calibrate these against the real chassis, degrees are geometry-dependent
STEERING_ANGLES = {
    "center": 0,
    "left1": -15,
    "left2": -30,
    "right1": 15,
    "right2": 30,
}
STEERING_SPEED = 300  # deg/s

# ponytail: calibrate speed/duration for the desired travel distance per step
DRIVE_SPEED = 500  # deg/s
DRIVE_STEP_MS = 1000  # default duration of one forward/back/turn step

TURN_PRESETS = {
    "turn_left1": "left1",
    "turn_left2": "left2",
    "turn_right1": "right1",
    "turn_right2": "right2",
}


def drive(speed, duration_ms):
    """Run both drive motors at the given speed for one timed step."""
    motor_back_left.run_time(speed, duration_ms, wait=False)
    motor_back_right.run_time(speed, duration_ms, wait=True)


def stop_drive():
    """Stop both drive motors immediately."""
    motor_back_left.stop()
    motor_back_right.stop()


def steer(preset):
    """Turn the steering motor to the given preset angle."""
    motor_front_steering_wheel.run_target(STEERING_SPEED, STEERING_ANGLES[preset])


def turn(preset, duration_ms):
    """Steer to the given preset angle and drive forward, so the chassis actually arcs."""
    steer(preset)
    drive(-DRIVE_SPEED, duration_ms)


def dispatch(command):
    """Run one command (optionally "name duration_ms"), returning the ack line sent back over BLE."""
    parts = command.split()
    if not parts:
        return "err empty cmd"
    name = parts[0]
    duration_ms = DRIVE_STEP_MS
    if len(parts) > 1:
        try:
            duration_ms = int(parts[1])
        except ValueError:
            return "err bad duration: " + command

    if name == "forward":
        drive(-DRIVE_SPEED, duration_ms)
    elif name == "back":
        drive(DRIVE_SPEED, duration_ms)
    elif name == "stop":
        stop_drive()
    elif name in STEERING_ANGLES:
        steer(name)
    elif name in TURN_PRESETS:
        turn(TURN_PRESETS[name], duration_ms)
    else:
        return "err unknown cmd: " + command
    return "ok " + command


def main():
    """Read commands from BLE stdin, one per line, until "quit"."""
    while True:
        line = stdin.readline().strip()
        if not line:
            continue
        if line == "quit":
            stop_drive()
            break
        print(dispatch(line))


if __name__ == "__main__":
    main()
