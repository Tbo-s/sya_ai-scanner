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


def _get_postflow_enabled() -> bool:
    return os.getenv("APP_GRBL_POSTFLOW_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def _get_postflow_sequence() -> str:
    return os.getenv("APP_GRBL_POSTFLOW_SEQUENCE", "$X|$H")


def is_safe_grbl_command(command: str) -> bool:
    command = command.strip()
    if not command:
        return False
    return GRBL_ALLOWED_CHARS.match(command) is not None


def send_grbl(command: str, wait_for_ok: bool = True) -> dict[str, Any]:
    normalized = command.strip()
    if not is_safe_grbl_command(normalized):
        raise HTTPException(status_code=400, detail="Invalid or unsafe GRBL command.")

    port = _get_grbl_port()
    baudrate = _get_grbl_baud()
    timeout_s = _get_grbl_read_timeout_s()
    try:
        with serial.Serial(port, baudrate, timeout=0.2) as ser:
            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()
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
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to talk to GRBL on {port}: {exc}") from exc


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


def z_up() -> dict[str, Any]:
    return send_grbl(f"G1 Z{float(os.getenv('APP_GRBL_Z_PICKUP', '30.0'))} F{_feed_rate()}")


def z_down() -> dict[str, Any]:
    return send_grbl(f"G1 Z{float(os.getenv('APP_GRBL_Z_TRAVEL', '5.0'))} F{_feed_rate()}")


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
    results = []
    for command in sequence:
        results.append(send_grbl(command, wait_for_ok=command != "!"))
    return {"executed": True, "sequence": sequence, "results": results}


def run_postflow_sequence(force: bool = False) -> dict[str, Any]:
    return run_sequence(_get_postflow_sequence(), enabled=force or _get_postflow_enabled())
