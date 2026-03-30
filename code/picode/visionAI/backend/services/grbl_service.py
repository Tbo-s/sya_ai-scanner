import os
import re
import time
from typing import Any

from fastapi import HTTPException
import serial  # type: ignore

import services.machine_service as _machine_svc


GRBL_ALLOWED_CHARS = re.compile(r"^[A-Za-z0-9\s\$\?\~\!\+\-\.\,\=\#\:\;\/\*\(\)]+$")


def _get_grbl_port() -> str:
    return os.getenv("APP_GRBL_PORT", "/dev/ttyACM1")


def _get_grbl_baud() -> int:
    return int(os.getenv("APP_GRBL_BAUD", "115200"))


def _get_grbl_read_timeout_s() -> float:
    return float(os.getenv("APP_GRBL_READ_TIMEOUT_S", "1.5"))


def _get_grbl_startup_delay_s() -> float:
    return float(os.getenv("APP_GRBL_STARTUP_DELAY_S", "2.0"))


def _get_postflow_enabled() -> bool:
    return os.getenv("APP_GRBL_POSTFLOW_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def _get_postflow_sequence() -> str:
    return os.getenv("APP_GRBL_POSTFLOW_SEQUENCE", "$X|$H")


def _get_test_spin_axis() -> str:
    axis = os.getenv("APP_GRBL_TEST_SPIN_AXIS", "X").strip().upper()
    return axis if axis in {"X", "Y", "Z"} else "X"


def _get_test_spin_distance() -> float:
    return float(os.getenv("APP_GRBL_TEST_SPIN_DISTANCE", "100000"))


def _get_test_spin_feed_rate() -> int:
    return int(os.getenv("APP_GRBL_TEST_SPIN_FEED_RATE", "300"))


def _get_manual_z_step() -> float:
    return float(os.getenv("APP_GRBL_MANUAL_Z_STEP", "1.0"))


def _get_manual_z_feed_rate() -> int:
    return int(os.getenv("APP_GRBL_MANUAL_Z_FEED_RATE", "120"))


def _get_manual_xy_step() -> float:
    return float(os.getenv("APP_GRBL_MANUAL_XY_STEP", "4.0"))


def _get_manual_xy_feed_rate() -> int:
    return int(os.getenv("APP_GRBL_MANUAL_XY_FEED_RATE", "300"))


def is_safe_grbl_command(command: str) -> bool:
    command = command.strip()
    if not command:
        return False
    return GRBL_ALLOWED_CHARS.match(command) is not None


def _normalize_command(command: str) -> str:
    normalized = command.strip()
    if not is_safe_grbl_command(normalized):
        raise HTTPException(status_code=400, detail="Invalid or unsafe GRBL command.")
    return normalized


def _prepare_grbl_serial(ser: serial.Serial) -> list[str]:
    startup_lines = []
    startup_delay_s = _get_grbl_startup_delay_s()
    if startup_delay_s > 0:
        time.sleep(startup_delay_s)

    started_at = time.time()
    while time.time() - started_at < 0.5:
        raw = ser.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", errors="ignore").strip()
        if text:
            startup_lines.append(text)

    if hasattr(ser, "reset_input_buffer"):
        ser.reset_input_buffer()

    return startup_lines


def _read_grbl_lines(ser: serial.Serial, duration_s: float) -> list[str]:
    lines = []
    started_at = time.time()
    while time.time() - started_at < duration_s:
        raw = ser.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", errors="ignore").strip()
        if text:
            lines.append(text)
    return lines


def _send_grbl_on_serial(ser: serial.Serial, command: str, wait_for_ok: bool = True) -> dict[str, Any]:
    normalized = _normalize_command(command)
    timeout_s = _get_grbl_read_timeout_s()

    ser.write((normalized + "\n").encode("ascii", errors="ignore"))
    if not wait_for_ok:
        return {"command": normalized, "ack": None, "response": []}

    started_at = time.time()
    lines = []
    while time.time() - started_at < timeout_s:
        raw = ser.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            continue
        lines.append(text)
        lowered = text.lower()
        if lowered == "ok":
            return {"command": normalized, "ack": "ok", "response": lines}
        if lowered.startswith("error"):
            raise HTTPException(
                status_code=400,
                detail={"command": normalized, "ack": "error", "response": lines},
            )
    raise HTTPException(status_code=504, detail=f"GRBL command timed out: {normalized}")


def _run_grbl_commands(commands: list[tuple[str, bool]]) -> list[dict[str, Any]]:
    port = _get_grbl_port()
    baudrate = _get_grbl_baud()

    try:
        with serial.Serial(port, baudrate, timeout=0.2) as ser:
            startup_lines = _prepare_grbl_serial(ser)
            results = []
            for index, (command, wait_for_ok) in enumerate(commands):
                result = _send_grbl_on_serial(ser, command, wait_for_ok=wait_for_ok)
                if index == 0 and startup_lines:
                    result["startup"] = startup_lines
                results.append(result)
            return results
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to talk to GRBL on {port}: {exc}") from exc


def send_grbl(command: str, wait_for_ok: bool = True) -> dict[str, Any]:
    return _run_grbl_commands([(command, wait_for_ok)])[0]


def _parse_sequence(raw_sequence: str) -> list[str]:
    parts = re.split(r"[|\n;]+", raw_sequence)
    return [part.strip() for part in parts if part.strip()]


def _feed_rate() -> int:
    return int(os.getenv("APP_GRBL_FEED_RATE", "3000"))


def move_to_front_of_phone() -> dict[str, Any]:
    x = float(os.getenv("APP_GRBL_FRONT_X", "50.0"))
    y = float(os.getenv("APP_GRBL_FRONT_Y", "100.0"))
    feed_rate = _feed_rate()
    return {"action": "move_to_front", "results": [send_grbl("G90"), send_grbl(f"G1 X{x} Y{y} F{feed_rate}")]}


def move_to_back_of_phone() -> dict[str, Any]:
    x = float(os.getenv("APP_GRBL_BACK_X", "50.0"))
    y = float(os.getenv("APP_GRBL_BACK_Y", "20.0"))
    feed_rate = _feed_rate()
    return {"action": "move_to_back", "results": [send_grbl("G90"), send_grbl(f"G1 X{x} Y{y} F{feed_rate}")]}


def _move_z_absolute(target_z: float, action: str) -> dict[str, Any]:
    feed_rate = _feed_rate()
    return {
        "action": action,
        "results": _run_grbl_commands(
            [
                ("G90", True),
                (f"G1 Z{target_z} F{feed_rate}", True),
            ]
        ),
    }


def _jog_z(delta_z: float, action: str) -> dict[str, Any]:
    feed_rate = _get_manual_z_feed_rate()
    return {
        "action": action,
        "results": _run_grbl_commands(
            [
                ("G91", True),
                (f"G1 Z{delta_z} F{feed_rate}", True),
                ("G90", True),
            ]
        ),
    }


def _jog_xy(delta_x: float, delta_y: float, action: str) -> dict[str, Any]:
    feed_rate = _get_manual_xy_feed_rate()
    return {
        "action": action,
        "results": _run_grbl_commands(
            [
                ("G91", True),
                (f"G1 X{delta_x} Y{delta_y} F{feed_rate}", True),
                ("G90", True),
            ]
        ),
    }


def z_up() -> dict[str, Any]:
    return _move_z_absolute(float(os.getenv("APP_GRBL_Z_PICKUP", "30.0")), "z_up")


def z_down() -> dict[str, Any]:
    return _move_z_absolute(float(os.getenv("APP_GRBL_Z_TRAVEL", "5.0")), "z_down")


def manual_z_up() -> dict[str, Any]:
    return _jog_z(abs(_get_manual_z_step()), "manual_z_up")


def manual_z_down() -> dict[str, Any]:
    return _jog_z(-abs(_get_manual_z_step()), "manual_z_down")


def manual_z_move(delta_z: float) -> dict[str, Any]:
    return _jog_z(float(delta_z), "manual_z_move")


def manual_xy_left() -> dict[str, Any]:
    return _jog_xy(-abs(_get_manual_xy_step()), 0.0, "manual_xy_left")


def manual_xy_right() -> dict[str, Any]:
    return _jog_xy(abs(_get_manual_xy_step()), 0.0, "manual_xy_right")


def manual_xy_forward() -> dict[str, Any]:
    return _jog_xy(0.0, abs(_get_manual_xy_step()), "manual_xy_forward")


def manual_xy_back() -> dict[str, Any]:
    return _jog_xy(0.0, -abs(_get_manual_xy_step()), "manual_xy_back")


def manual_xy_move(delta_x: float, delta_y: float) -> dict[str, Any]:
    return _jog_xy(float(delta_x), float(delta_y), "manual_xy_move")


def feed_hold() -> dict[str, Any]:
    return send_grbl("!", wait_for_ok=False)


def _get_distance_threshold() -> int:
    return int(os.getenv("APP_ARM_DISTANCE_THRESHOLD_CM", "3"))


def _move_with_distance_stop(x: float, y: float, action: str) -> dict[str, Any]:
    slow_feed = max(200, _feed_rate() // 6)
    threshold = _get_distance_threshold()
    send_grbl("G90", wait_for_ok=True)
    send_grbl(f"G1 X{x} Y{y} F{slow_feed}", wait_for_ok=False)
    for _ in range(200):
        result = _machine_svc.read_distance()
        distance = result.get("distance_cm", -1)
        if 0 < distance <= threshold:
            feed_hold()
            return {"action": action, "stopped": True, "distance_cm": distance}
        time.sleep(0.1)
    feed_hold()
    raise HTTPException(status_code=504, detail=f"{action} timed out waiting for distance threshold.")


def move_to_front_slow_with_distance_stop() -> dict[str, Any]:
    return _move_with_distance_stop(
        float(os.getenv("APP_GRBL_FRONT_X", "50.0")),
        float(os.getenv("APP_GRBL_FRONT_Y", "100.0")),
        "move_front_distance_stop",
    )


def move_to_back_slow_with_distance_stop() -> dict[str, Any]:
    return _move_with_distance_stop(
        float(os.getenv("APP_GRBL_BACK_X", "50.0")),
        float(os.getenv("APP_GRBL_BACK_Y", "20.0")),
        "move_back_distance_stop",
    )


def run_sequence(raw_sequence: str, enabled: bool = True) -> dict[str, Any]:
    if not enabled:
        return {
            "executed": False,
            "reason": "disabled",
            "sequence": _parse_sequence(raw_sequence),
            "results": [],
        }

    sequence = _parse_sequence(raw_sequence)
    results = _run_grbl_commands([(command, command != "!") for command in sequence])
    return {"executed": True, "sequence": sequence, "results": results}


def run_postflow_sequence(force: bool = False) -> dict[str, Any]:
    return run_sequence(_get_postflow_sequence(), enabled=force or _get_postflow_enabled())


def start_test_spin() -> dict[str, Any]:
    axis = _get_test_spin_axis()
    distance = _get_test_spin_distance()
    feed_rate = _get_test_spin_feed_rate()
    results = _run_grbl_commands(
        [
            ("$X", True),
            ("G91", True),
            (f"G1 {axis}{distance} F{feed_rate}", False),
        ]
    )
    return {
        "started": True,
        "axis": axis,
        "distance": distance,
        "feed_rate": feed_rate,
        "results": results,
    }


def stop_test_spin() -> dict[str, Any]:
    port = _get_grbl_port()
    baudrate = _get_grbl_baud()

    try:
        with serial.Serial(port, baudrate, timeout=0.2) as ser:
            startup_lines = _prepare_grbl_serial(ser)
            results = []

            results.append(_send_grbl_on_serial(ser, "!", wait_for_ok=False))
            time.sleep(0.25)

            ser.write(b"\x18")
            reset_lines = _read_grbl_lines(ser, max(0.5, _get_grbl_startup_delay_s()))

            unlock_result = _send_grbl_on_serial(ser, "$X", wait_for_ok=True)
            absolute_result = _send_grbl_on_serial(ser, "G90", wait_for_ok=True)

            if startup_lines:
                results[0]["startup"] = startup_lines
            if reset_lines:
                unlock_result["reset"] = reset_lines

            results.extend([unlock_result, absolute_result])
            return {"stopped": True, "results": results}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to talk to GRBL on {port}: {exc}") from exc
