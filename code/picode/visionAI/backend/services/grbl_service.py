import atexit
import glob
import math
import os
import re
import threading
import time
from typing import Any, Optional

from fastapi import HTTPException
import serial  # type: ignore

import services.machine_service as _machine_svc


GRBL_ALLOWED_CHARS = re.compile(r"^[A-Za-z0-9\s\$\?\~\!\+\-\.\,\=\#\:\;\/\*\(\)]+$")
_GRBL_SERIAL_LOCK = threading.Lock()
_GRBL_SERIAL: Optional[serial.Serial] = None
_GRBL_SERIAL_PORT: Optional[str] = None
_GRBL_SERIAL_BAUD: Optional[int] = None
_ARM_POSITION_LOCK = threading.Lock()
_ARM_XY_POSITION: dict[str, Optional[float]] = {"x": None, "y": None}
_ARM_HOMED = False
_LAST_GRBL_STATUS: Optional[dict[str, Any]] = None
_LAST_GRBL_STATUS_AT: Optional[float] = None
_LIMIT_AXES = ("x", "y", "z")
_XY_AXES = ("x", "y")


def _get_grbl_port() -> str:
    return os.getenv("APP_GRBL_PORT", "/dev/ttyACM1")


def _get_grbl_baud() -> int:
    return int(os.getenv("APP_GRBL_BAUD", "115200"))


def _get_grbl_read_timeout_s() -> float:
    return float(os.getenv("APP_GRBL_READ_TIMEOUT_S", "1.5"))


def _get_grbl_motion_timeout_s() -> float:
    return float(os.getenv("APP_GRBL_MOTION_TIMEOUT_S", "5.0"))


def _get_grbl_status_timeout_s() -> float:
    return max(0.1, float(os.getenv("APP_GRBL_STATUS_TIMEOUT_S", "1.0")))


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
    return float(os.getenv("APP_GRBL_MANUAL_XY_STEP", "0.5"))


def _get_manual_xy_feed_rate() -> int:
    return int(os.getenv("APP_GRBL_MANUAL_XY_FEED_RATE", "120"))


def _get_xy_max(axis: str) -> float:
    normalized_axis = axis.upper()
    default_max = "5.5" if normalized_axis == "Y" else "4.0"
    return max(0.0, float(os.getenv(f"APP_GRBL_MAX_{normalized_axis}", default_max)))


def _get_home_xy_feed_rate() -> int:
    return int(os.getenv("APP_GRBL_HOME_XY_FEED_RATE", "60"))


def _get_home_xy_search_distance() -> float:
    return abs(float(os.getenv("APP_GRBL_HOME_XY_SEARCH_DISTANCE", "1000.0")))


def _get_home_xy_axis_order() -> list[str]:
    raw_order = os.getenv("APP_GRBL_HOME_XY_AXIS_ORDER", "X,Y")
    order = []
    for axis in re.split(r"[\s,|;]+", raw_order.strip().upper()):
        if axis in {"X", "Y"} and axis.lower() not in order:
            order.append(axis.lower())
    return order or ["x", "y"]


def _get_home_z_clearance() -> float:
    return abs(float(os.getenv("APP_GRBL_HOME_Z_CLEARANCE", "2.0")))


def _get_home_z_step() -> float:
    return abs(float(os.getenv("APP_GRBL_HOME_Z_STEP", "1.0")))


def _get_home_z_search_distance() -> float:
    return abs(float(os.getenv("APP_GRBL_HOME_Z_SEARCH_DISTANCE", "100.0")))


def _get_home_z_feed_rate() -> int:
    return int(os.getenv("APP_GRBL_HOME_Z_FEED_RATE", "30"))


def _is_z_axis_enabled() -> bool:
    return os.getenv("APP_GRBL_Z_AXIS_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}


def _z_axis_disabled_report(action: str, **extra: Any) -> dict[str, Any]:
    return {
        "action": action,
        "axis": "z",
        "skipped": True,
        "disabled": True,
        "reason": "z_axis_disabled",
        "results": [],
        **extra,
    }


def _get_limit_toward_zero_sign(axis: str) -> int:
    raw = os.getenv(f"APP_GRBL_{axis.upper()}_LIMIT_TOWARD_ZERO_SIGN", "-1").strip().lower()
    return 1 if raw in {"1", "+1", "+", "positive", "pos"} else -1


def _limit_defaults() -> dict[str, bool]:
    return {axis: False for axis in _LIMIT_AXES}


def _limit_toward_zero_signs() -> dict[str, int]:
    return {axis: _get_limit_toward_zero_sign(axis.upper()) for axis in _LIMIT_AXES}


def _get_limit_pin_mode() -> str:
    mode = os.getenv("APP_GRBL_LIMIT_PIN_MODE", "active_present").strip().lower()
    if mode in {"active_absent", "absent", "raw_high", "inverted"}:
        return "active_absent"
    return "active_present"


def _get_configure_nc_limits_enabled() -> bool:
    return os.getenv("APP_GRBL_CONFIGURE_NC_LIMITS", "1").strip().lower() in {"1", "true", "yes", "on"}


def _get_limit_pins_invert_value() -> int:
    raw = os.getenv("APP_GRBL_LIMIT_PINS_INVERT", "1").strip().lower()
    return 1 if raw in {"1", "true", "yes", "on"} else 0


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


def _parse_grbl_position(value: str) -> Optional[dict[str, float]]:
    parts = value.split(",")
    if len(parts) < 3:
        return None

    try:
        return {
            "x": float(parts[0]),
            "y": float(parts[1]),
            "z": float(parts[2]),
        }
    except ValueError:
        return None


def _parse_limit_state_from_pin_field(pin_state: str, pin_field_seen: bool) -> tuple[dict[str, bool], list[str]]:
    pins = pin_state.upper()
    mode = _get_limit_pin_mode()
    limits: dict[str, bool] = {}

    for axis in _LIMIT_AXES:
        pin_present = axis.upper() in pins
        if mode == "active_absent":
            limits[axis] = not pin_present if pin_field_seen else False
        else:
            limits[axis] = pin_present

    return limits, [axis for axis in _LIMIT_AXES if limits[axis]]


def _parse_grbl_status_line(line: str) -> Optional[dict[str, Any]]:
    stripped = line.strip()
    if not stripped.startswith("<") or not stripped.endswith(">"):
        return None

    fields = stripped[1:-1].split("|")
    if not fields or not fields[0]:
        return None

    parsed: dict[str, Any] = {
        "raw": stripped,
        "state": fields[0],
        "machine_position": None,
        "work_position": None,
        "pin_state": "",
        "pin_state_seen": False,
        "limit_axes": [],
        "limits": _limit_defaults(),
    }

    pin_state = ""
    pin_field_seen = False

    for field in fields[1:]:
        if ":" not in field:
            continue
        key, value = field.split(":", 1)
        if key == "MPos":
            parsed["machine_position"] = _parse_grbl_position(value)
        elif key == "WPos":
            parsed["work_position"] = _parse_grbl_position(value)
        elif key == "Pn":
            pin_state = value.upper()
            pin_field_seen = True

    limits, limit_axes = _parse_limit_state_from_pin_field(pin_state, pin_field_seen)
    parsed["pin_state"] = pin_state
    parsed["pin_state_seen"] = pin_field_seen
    parsed["limits"] = limits
    parsed["limit_axes"] = limit_axes

    return parsed


def _read_grbl_status_on_serial(ser: serial.Serial) -> dict[str, Any]:
    timeout_s = _get_grbl_status_timeout_s()
    started_at = time.time()
    lines: list[str] = []

    ser.write(b"?")

    while time.time() - started_at < timeout_s:
        raw = ser.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            continue

        lines.append(text)
        parsed = _parse_grbl_status_line(text)
        if parsed is not None:
            parsed["response"] = lines
            return parsed

    raise HTTPException(status_code=504, detail="GRBL status timed out.")


def _status_position(status: Optional[dict[str, Any]]) -> dict[str, Optional[float]]:
    with _ARM_POSITION_LOCK:
        tracked = dict(_ARM_XY_POSITION)
        homed = _ARM_HOMED

    position: dict[str, Optional[float]] = {"x": None, "y": None, "z": None}
    if not status:
        return {
            "x": tracked.get("x"),
            "y": tracked.get("y"),
            "z": None,
        }

    limits = status.get("limits") or {}
    grbl_position = status.get("work_position") or status.get("machine_position") or {}

    for axis in _XY_AXES:
        if homed and limits.get(axis):
            position[axis] = 0.0
        elif tracked.get(axis) is not None:
            position[axis] = tracked[axis]
        elif isinstance(grbl_position, dict) and grbl_position.get(axis) is not None:
            position[axis] = max(0.0, float(grbl_position[axis]))

    if limits.get("z"):
        position["z"] = 0.0
    elif isinstance(grbl_position, dict) and grbl_position.get("z") is not None:
        position["z"] = max(0.0, float(grbl_position["z"]))

    return position


def _apply_status_limits_to_tracked_position(status: Optional[dict[str, Any]]) -> None:
    if not status:
        return

    limits = status.get("limits") or {}
    with _ARM_POSITION_LOCK:
        if not _ARM_HOMED:
            return
        for axis in _XY_AXES:
            if limits.get(axis):
                _ARM_XY_POSITION[axis] = 0.0


def _cache_grbl_status(status: dict[str, Any]) -> None:
    global _LAST_GRBL_STATUS, _LAST_GRBL_STATUS_AT

    _LAST_GRBL_STATUS = {
        "raw": status.get("raw"),
        "state": status.get("state"),
        "machine_position": dict(status.get("machine_position") or {}) or None,
        "work_position": dict(status.get("work_position") or {}) or None,
        "pin_state": status.get("pin_state", ""),
        "pin_state_seen": bool(status.get("pin_state_seen")),
        "limit_axes": list(status.get("limit_axes") or []),
        "limits": dict(status.get("limits") or _limit_defaults()),
        "position": dict(status.get("position") or {}),
        "homed": bool(status.get("homed")),
        "soft_limits": dict(status.get("soft_limits") or _xy_soft_limits()),
        "limit_toward_zero_sign": dict(
            status.get("limit_toward_zero_sign") or _limit_toward_zero_signs()
        ),
        "limit_pin_mode": status.get("limit_pin_mode", _get_limit_pin_mode()),
        "response": list(status.get("response") or []),
    }
    _LAST_GRBL_STATUS_AT = time.time()


def _enrich_live_grbl_status(status: dict[str, Any], startup_lines: Optional[list[str]] = None) -> dict[str, Any]:
    if startup_lines:
        status["startup"] = startup_lines
    _apply_status_limits_to_tracked_position(status)
    status["position"] = _status_position(status)
    with _ARM_POSITION_LOCK:
        status["homed"] = _ARM_HOMED
    status["soft_limits"] = _xy_soft_limits()
    status["limit_toward_zero_sign"] = _limit_toward_zero_signs()
    status["limit_pin_mode"] = _get_limit_pin_mode()
    status["cached"] = False
    status["stale"] = False
    status["cache_age_ms"] = 0
    _cache_grbl_status(status)
    return status


def _build_cached_grbl_status(reason: str) -> dict[str, Any]:
    cached = dict(_LAST_GRBL_STATUS or {})
    tracked_position = _status_position(None)

    position = dict(cached.get("position") or {})
    for axis in _XY_AXES:
        if position.get(axis) is None:
            position[axis] = tracked_position.get(axis)
    if position.get("z") is None:
        position["z"] = tracked_position.get("z")

    with _ARM_POSITION_LOCK:
        homed = _ARM_HOMED

    age_ms: Optional[int] = None
    if _LAST_GRBL_STATUS_AT is not None:
        age_ms = max(0, int((time.time() - _LAST_GRBL_STATUS_AT) * 1000))

    return {
        "raw": cached.get("raw"),
        "state": cached.get("state", "Unknown"),
        "machine_position": cached.get("machine_position"),
        "work_position": cached.get("work_position"),
        "pin_state": cached.get("pin_state", ""),
        "pin_state_seen": bool(cached.get("pin_state_seen")),
        "limit_axes": list(cached.get("limit_axes") or []),
        "limits": dict(cached.get("limits") or _limit_defaults()),
        "position": position,
        "homed": homed,
        "soft_limits": dict(cached.get("soft_limits") or _xy_soft_limits()),
        "limit_toward_zero_sign": dict(
            cached.get("limit_toward_zero_sign") or _limit_toward_zero_signs()
        ),
        "limit_pin_mode": cached.get("limit_pin_mode", _get_limit_pin_mode()),
        "response": list(cached.get("response") or []),
        "cached": True,
        "stale": True,
        "cache_age_ms": age_ms,
        "status_error": reason,
    }


def _set_arm_unhomed() -> None:
    global _ARM_HOMED

    with _ARM_POSITION_LOCK:
        _ARM_HOMED = False
        _ARM_XY_POSITION["x"] = None
        _ARM_XY_POSITION["y"] = None


def _set_arm_axis_zero(axis: str) -> None:
    global _ARM_HOMED

    with _ARM_POSITION_LOCK:
        _ARM_XY_POSITION[axis] = 0.0
        if _ARM_XY_POSITION["x"] == 0.0 and _ARM_XY_POSITION["y"] == 0.0:
            _ARM_HOMED = True


def _set_arm_homed_zero() -> None:
    global _ARM_HOMED

    with _ARM_POSITION_LOCK:
        _ARM_HOMED = True
        _ARM_XY_POSITION["x"] = 0.0
        _ARM_XY_POSITION["y"] = 0.0


def _get_tracked_xy_position() -> dict[str, Any]:
    with _ARM_POSITION_LOCK:
        return {
            "homed": _ARM_HOMED,
            "x": _ARM_XY_POSITION["x"],
            "y": _ARM_XY_POSITION["y"],
        }


def _xy_soft_limits() -> dict[str, float]:
    return {
        "x": _get_xy_max("X"),
        "y": _get_xy_max("Y"),
    }


def _clamp_xy_delta_to_soft_limits(delta_x: float, delta_y: float) -> dict[str, Any]:
    tracked = _get_tracked_xy_position()
    limits = _xy_soft_limits()
    adjusted = {"x": float(delta_x), "y": float(delta_y)}

    if not tracked["homed"]:
        return {
            "delta_x": adjusted["x"],
            "delta_y": adjusted["y"],
            "bounded": False,
            "skipped": False,
            "soft_limits": limits,
            "target": {"x": tracked["x"], "y": tracked["y"]},
        }

    target: dict[str, Optional[float]] = {"x": tracked["x"], "y": tracked["y"]}
    bounded = False

    for axis, delta in (("x", delta_x), ("y", delta_y)):
        current = tracked[axis]
        if current is None:
            continue

        requested_target = current + float(delta)
        clamped_target = min(max(0.0, requested_target), limits[axis])
        adjusted[axis] = clamped_target - current
        target[axis] = clamped_target
        if abs(adjusted[axis] - float(delta)) > 1e-9:
            bounded = True

    return {
        "delta_x": adjusted["x"],
        "delta_y": adjusted["y"],
        "bounded": bounded,
        "skipped": abs(adjusted["x"]) <= 1e-9 and abs(adjusted["y"]) <= 1e-9,
        "soft_limits": limits,
        "target": target,
    }


def _clamp_xy_target_to_soft_limits(x: float, y: float) -> dict[str, Any]:
    limits = _xy_soft_limits()
    target_x = min(max(0.0, float(x)), limits["x"])
    target_y = min(max(0.0, float(y)), limits["y"])

    return {
        "x": target_x,
        "y": target_y,
        "bounded": abs(target_x - float(x)) > 1e-9 or abs(target_y - float(y)) > 1e-9,
        "requested": {"x": float(x), "y": float(y)},
        "soft_limits": limits,
    }


def _apply_xy_delta_to_tracked_position(delta_x: float, delta_y: float, limit_axes: set[str]) -> None:
    with _ARM_POSITION_LOCK:
        if "x" in limit_axes:
            _ARM_XY_POSITION["x"] = 0.0
        elif abs(delta_x) > 1e-9 and _ARM_XY_POSITION["x"] is not None:
            _ARM_XY_POSITION["x"] = min(_get_xy_max("X"), max(0.0, _ARM_XY_POSITION["x"] + delta_x))

        if "y" in limit_axes:
            _ARM_XY_POSITION["y"] = 0.0
        elif abs(delta_y) > 1e-9 and _ARM_XY_POSITION["y"] is not None:
            _ARM_XY_POSITION["y"] = min(_get_xy_max("Y"), max(0.0, _ARM_XY_POSITION["y"] + delta_y))


def _delta_moves_toward_zero(axis: str, delta: float) -> bool:
    if abs(delta) <= 1e-9:
        return False
    sign = _get_limit_toward_zero_sign(axis)
    return delta > 0 if sign > 0 else delta < 0


def _limit_stop_axes_for_xy_delta(delta_x: float, delta_y: float) -> set[str]:
    axes = set()
    if _delta_moves_toward_zero("X", delta_x):
        axes.add("x")
    if _delta_moves_toward_zero("Y", delta_y):
        axes.add("y")
    return axes


def _moving_axes_for_xy_delta(delta_x: float, delta_y: float) -> set[str]:
    axes = set()
    if abs(delta_x) > 1e-9:
        axes.add("x")
    if abs(delta_y) > 1e-9:
        axes.add("y")
    return axes


def _limit_result_from_status(status: dict[str, Any], checked_axes: set[str]) -> Optional[dict[str, Any]]:
    active_axes = set(status.get("limit_axes") or [])
    triggered_axes = active_axes & checked_axes
    if not triggered_axes:
        return None

    return {
        "command": "?",
        "ack": "limit",
        "response": status.get("response", []),
        "limit_triggered": True,
        "limit_axes": sorted(triggered_axes),
        "status": status,
    }


def _stop_grbl_motion_for_limit(ser: serial.Serial) -> dict[str, Any]:
    stop_report: dict[str, Any] = {"feed_hold_sent": False, "soft_reset_sent": False}

    try:
        ser.write(b"!")
        stop_report["feed_hold_sent"] = True
    except Exception as exc:
        stop_report["feed_hold_error"] = str(exc)

    time.sleep(0.05)

    try:
        ser.write(b"\x18")
        stop_report["soft_reset_sent"] = True
        stop_report["reset_response"] = _read_grbl_lines(ser, max(0.5, _get_grbl_startup_delay_s()))
    except Exception as exc:
        stop_report["soft_reset_error"] = str(exc)

    try:
        stop_report["unlock"] = _send_grbl_on_serial(ser, "$X", wait_for_ok=True)
    except HTTPException as exc:
        stop_report["unlock_error"] = exc.detail

    try:
        stop_report["absolute"] = _send_grbl_on_serial(ser, "G90", wait_for_ok=True)
    except HTTPException as exc:
        stop_report["absolute_error"] = exc.detail

    return stop_report


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


def _extract_grbl_state(line: str) -> Optional[str]:
    stripped = line.strip()
    if not stripped.startswith("<") or not stripped.endswith(">"):
        return None
    body = stripped[1:-1]
    if not body:
        return None
    return body.split("|", 1)[0].strip() or None


def _wait_for_grbl_idle(
    ser: serial.Serial,
    limit_stop_axes: Optional[set[str]] = None,
    moving_limit_axes: Optional[set[str]] = None,
    initial_limit_axes: Optional[set[str]] = None,
) -> dict[str, Any]:
    timeout_s = _get_grbl_motion_timeout_s()
    read_timeout_s = _get_grbl_read_timeout_s()
    started_at = time.time()
    lines: list[str] = []
    checked_limit_axes = limit_stop_axes or set()
    checked_moving_axes = moving_limit_axes or set()
    starting_limit_axes = initial_limit_axes or set()

    while time.time() - started_at < timeout_s:
        ser.write(b"?")

        status_started_at = time.time()
        while time.time() - status_started_at < read_timeout_s:
            raw = ser.readline()
            if not raw:
                continue

            text = raw.decode("utf-8", errors="ignore").strip()
            if not text:
                continue

            lines.append(text)
            lowered = text.lower()
            if lowered.startswith("alarm") and checked_moving_axes:
                return {
                    "command": "?",
                    "ack": "alarm_limit",
                    "response": lines,
                    "limit_triggered": True,
                    "limit_axes": sorted(checked_moving_axes),
                    "state": "Alarm",
                    "stop": _stop_grbl_motion_for_limit(ser),
                }

            parsed = _parse_grbl_status_line(text)
            state = parsed["state"] if parsed else _extract_grbl_state(text)
            if state is None:
                continue

            if parsed is not None:
                parsed["response"] = lines
                limit_result = _limit_result_from_status(parsed, checked_limit_axes)
                if limit_result is None:
                    active_axes = set(parsed.get("limit_axes") or [])
                    newly_active_axes = (active_axes & checked_moving_axes) - starting_limit_axes
                    if newly_active_axes:
                        limit_result = {
                            "command": "?",
                            "ack": "limit",
                            "response": lines,
                            "limit_triggered": True,
                            "limit_axes": sorted(newly_active_axes),
                            "status": parsed,
                        }
                if limit_result is not None:
                    limit_result["state"] = state
                    if state != "Idle":
                        limit_result["stop"] = _stop_grbl_motion_for_limit(ser)
                    return limit_result

            if state == "Idle":
                return {"state": state, "response": lines}
            if state == "Alarm":
                raise HTTPException(
                    status_code=400,
                    detail={"command": "?", "ack": "alarm", "response": lines},
                )
            break

        time.sleep(0.05)

    raise HTTPException(status_code=504, detail="GRBL motion timed out waiting for idle.")


def _close_grbl_serial_locked() -> None:
    global _GRBL_SERIAL, _GRBL_SERIAL_PORT, _GRBL_SERIAL_BAUD

    if _GRBL_SERIAL is not None:
        try:
            _GRBL_SERIAL.close()
        except Exception:
            pass

    _GRBL_SERIAL = None
    _GRBL_SERIAL_PORT = None
    _GRBL_SERIAL_BAUD = None


def _close_grbl_serial() -> None:
    with _GRBL_SERIAL_LOCK:
        _close_grbl_serial_locked()


def _is_auto_grbl_port(port: str) -> bool:
    return port.strip().lower() in {"", "auto", "detect"}


def _dedupe_serial_ports(ports: list[str]) -> list[str]:
    seen = set()
    unique = []
    for port in ports:
        key = os.path.realpath(port) if os.path.exists(port) else port
        if key in seen:
            continue
        seen.add(key)
        unique.append(port)
    return unique


def _candidate_grbl_ports(configured_port: str) -> list[str]:
    ports = []
    if not _is_auto_grbl_port(configured_port):
        ports.append(configured_port)

    ports.extend(sorted(glob.glob("/dev/serial/by-id/*")))
    ports.extend(sorted(glob.glob("/dev/ttyUSB*")))
    ports.extend(sorted(glob.glob("/dev/ttyACM*")))
    return _dedupe_serial_ports(ports)


def _serial_looks_like_grbl(ser: serial.Serial, startup_lines: list[str]) -> bool:
    if any("grbl" in line.lower() for line in startup_lines):
        return True

    try:
        if hasattr(ser, "reset_input_buffer"):
            ser.reset_input_buffer()
        ser.write(b"?")

        started_at = time.time()
        while time.time() - started_at < max(0.5, _get_grbl_status_timeout_s()):
            raw = ser.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="ignore").strip()
            if not text:
                continue
            if "grbl" in text.lower() or _parse_grbl_status_line(text) is not None:
                return True
    except Exception:
        return False

    return False


def _open_grbl_serial(port: str, baudrate: int) -> tuple[serial.Serial, list[str]]:
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baudrate
    ser.timeout = 0.2

    # Keep the Mega from being reset on every open/close cycle.
    for line_signal in ("dtr", "rts"):
        if hasattr(ser, line_signal):
            try:
                setattr(ser, line_signal, False)
            except Exception:
                pass

    ser.open()

    for line_signal in ("dtr", "rts"):
        if hasattr(ser, line_signal):
            try:
                setattr(ser, line_signal, False)
            except Exception:
                pass

    if hasattr(ser, "reset_output_buffer"):
        ser.reset_output_buffer()

    startup_lines = _prepare_grbl_serial(ser)
    return ser, startup_lines


def _ensure_grbl_serial() -> tuple[serial.Serial, list[str]]:
    global _GRBL_SERIAL, _GRBL_SERIAL_PORT, _GRBL_SERIAL_BAUD

    configured_port = _get_grbl_port()
    candidate_ports = _candidate_grbl_ports(configured_port)
    baudrate = _get_grbl_baud()

    if _GRBL_SERIAL is not None:
        same_port = _GRBL_SERIAL_PORT in candidate_ports and _GRBL_SERIAL_BAUD == baudrate
        if same_port and getattr(_GRBL_SERIAL, "is_open", False):
            return _GRBL_SERIAL, []
        _close_grbl_serial_locked()

    attempts = []
    for port in candidate_ports:
        try:
            ser, startup_lines = _open_grbl_serial(port, baudrate)
            if not _serial_looks_like_grbl(ser, startup_lines):
                attempts.append(f"{port}: no GRBL response")
                try:
                    ser.close()
                except Exception:
                    pass
                continue

            _GRBL_SERIAL = ser
            _GRBL_SERIAL_PORT = port
            _GRBL_SERIAL_BAUD = baudrate
            return ser, startup_lines
        except Exception as exc:
            attempts.append(f"{port}: {exc}")
            _close_grbl_serial_locked()

    detail = "No candidate GRBL serial ports found."
    if attempts:
        detail = "Failed to find GRBL controller. Attempts: " + "; ".join(attempts)
    raise HTTPException(status_code=500, detail=detail)


atexit.register(_close_grbl_serial)


def _run_grbl_commands(
    commands: list[tuple[str, bool]],
    wait_for_idle: bool = False,
    precheck_limit_axes: Optional[set[str]] = None,
    limit_stop_axes: Optional[set[str]] = None,
    observe_limit_axes: Optional[set[str]] = None,
    require_limit_precheck: bool = False,
) -> list[dict[str, Any]]:
    port = _get_grbl_port()

    with _GRBL_SERIAL_LOCK:
        try:
            ser, startup_lines = _ensure_grbl_serial()
            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()

            initial_limit_axes: set[str] = set()
            if precheck_limit_axes or observe_limit_axes:
                try:
                    status = _read_grbl_status_on_serial(ser)
                    _apply_status_limits_to_tracked_position(status)
                    initial_limit_axes = set(status.get("limit_axes") or []) & (observe_limit_axes or set())
                    if precheck_limit_axes:
                        limit_result = _limit_result_from_status(status, precheck_limit_axes)
                        if limit_result is not None:
                            if startup_lines:
                                limit_result["startup"] = startup_lines
                            return [limit_result]
                except HTTPException as exc:
                    if require_limit_precheck and precheck_limit_axes:
                        raise HTTPException(
                            status_code=exc.status_code,
                            detail=f"Cannot verify GRBL limit switches before motion: {exc.detail}",
                        ) from exc
                    # If realtime status is unavailable, still send non-critical jog commands.
                    # The movement command itself will surface serial/GRBL failures.
                    pass

            results = []
            for index, (command, wait_for_ok) in enumerate(commands):
                result = _send_grbl_on_serial(ser, command, wait_for_ok=wait_for_ok)
                if index == 0 and startup_lines:
                    result["startup"] = startup_lines
                results.append(result)
            if wait_for_idle:
                idle_result = _wait_for_grbl_idle(
                    ser,
                    limit_stop_axes=limit_stop_axes,
                    moving_limit_axes=observe_limit_axes,
                    initial_limit_axes=initial_limit_axes,
                )
                if results:
                    results[-1]["idle"] = idle_result
            return results
        except HTTPException as exc:
            if exc.status_code >= 500:
                _close_grbl_serial_locked()
            raise
        except Exception as exc:
            _close_grbl_serial_locked()
            raise HTTPException(status_code=500, detail=f"Failed to talk to GRBL on {port}: {exc}") from exc


def send_grbl(command: str, wait_for_ok: bool = True) -> dict[str, Any]:
    return _run_grbl_commands([(command, wait_for_ok)])[0]


def ensure_nc_limit_pin_setting() -> dict[str, Any]:
    if not _get_configure_nc_limits_enabled():
        return {"configured": False, "reason": "disabled"}

    port = _get_grbl_port()
    target = _get_limit_pins_invert_value()

    with _GRBL_SERIAL_LOCK:
        try:
            ser, startup_lines = _ensure_grbl_serial()
            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()

            settings = _send_grbl_on_serial(ser, "$$", wait_for_ok=True)
            if startup_lines:
                settings["startup"] = startup_lines

            current: Optional[int] = None
            for line in settings.get("response", []):
                match = re.match(r"^\$5=(\d+)", line.strip())
                if match:
                    current = int(match.group(1))
                    break

            if current == target:
                return {"configured": False, "setting": "$5", "value": current, "settings": settings}

            set_result = _send_grbl_on_serial(ser, f"$5={target}", wait_for_ok=True)
            return {
                "configured": True,
                "setting": "$5",
                "previous": current,
                "value": target,
                "settings": settings,
                "result": set_result,
            }
        except HTTPException as exc:
            if exc.status_code >= 500:
                _close_grbl_serial_locked()
            raise
        except Exception as exc:
            _close_grbl_serial_locked()
            raise HTTPException(status_code=500, detail=f"Failed to configure GRBL NC limits on {port}: {exc}") from exc


def get_grbl_arm_status() -> dict[str, Any]:
    port = _get_grbl_port()

    with _GRBL_SERIAL_LOCK:
        try:
            ser, startup_lines = _ensure_grbl_serial()
            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()

            status = _read_grbl_status_on_serial(ser)
            return _enrich_live_grbl_status(status, startup_lines=startup_lines)
        except HTTPException as exc:
            if exc.status_code == 504:
                return _build_cached_grbl_status(str(exc.detail))
            if exc.status_code >= 500:
                _close_grbl_serial_locked()
            raise
        except Exception as exc:
            _close_grbl_serial_locked()
            raise HTTPException(status_code=500, detail=f"Failed to read GRBL status on {port}: {exc}") from exc


def _extract_limit_axes_from_results(results: list[dict[str, Any]]) -> set[str]:
    limit_axes: set[str] = set()
    for result in results:
        if result.get("limit_triggered"):
            limit_axes.update(result.get("limit_axes") or [])
        idle = result.get("idle")
        if isinstance(idle, dict) and idle.get("limit_triggered"):
            limit_axes.update(idle.get("limit_axes") or [])
    return limit_axes


def _read_homing_limit_precheck() -> dict[str, Any]:
    port = _get_grbl_port()
    with _GRBL_SERIAL_LOCK:
        try:
            ser, startup_lines = _ensure_grbl_serial()
            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()

            status = _read_grbl_status_on_serial(ser)
            status = _enrich_live_grbl_status(status, startup_lines=startup_lines)
            status["homing_precheck"] = True
            return status
        except HTTPException as exc:
            if exc.status_code >= 500:
                _close_grbl_serial_locked()
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"Cannot verify GRBL limit switches before homing: {exc.detail}",
            ) from exc
        except Exception as exc:
            _close_grbl_serial_locked()
            raise HTTPException(
                status_code=500,
                detail=f"Cannot verify GRBL limit switches before homing on {port}: {exc}",
            ) from exc


def _home_xy_axis(axis: str, precheck_status: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    axis = axis.lower()
    if axis not in {"x", "y"}:
        raise HTTPException(status_code=400, detail=f"Unsupported homing axis: {axis}")

    status = precheck_status or _read_homing_limit_precheck()
    if (status.get("limits") or {}).get(axis):
        _set_arm_axis_zero(axis)
        return {
            "axis": axis,
            "already_at_limit": True,
            "stopped_by_limit": True,
            "limit_axes": [axis],
            "status": status,
        }

    feed_rate = _get_home_xy_feed_rate()
    distance = _get_home_xy_search_distance() * _get_limit_toward_zero_sign(axis)
    command_axis = axis.upper()
    moving_axes = {axis}
    results = _run_grbl_commands(
        [
            ("G21", True),
            ("G91", True),
            (f"G1 {command_axis}{distance} F{feed_rate}", True),
        ],
        wait_for_idle=True,
        precheck_limit_axes=moving_axes,
        observe_limit_axes=moving_axes,
        require_limit_precheck=True,
    )
    limit_axes = _extract_limit_axes_from_results(results)
    if axis not in limit_axes:
        _set_arm_unhomed()
        raise HTTPException(
            status_code=504,
            detail=f"XY homing failed: {axis.upper()} limit was not reached within {abs(distance)} mm.",
        )

    _set_arm_axis_zero(axis)
    return {
        "axis": axis,
        "already_at_limit": False,
        "stopped_by_limit": True,
        "limit_axes": sorted(limit_axes),
        "feed_rate": feed_rate,
        "distance": distance,
        "results": results,
    }


def _unlock_grbl_if_needed() -> Optional[dict[str, Any]]:
    try:
        return send_grbl("$X", wait_for_ok=True)
    except HTTPException:
        # $X is only needed when the controller booted in alarm/lock state.
        return None


def _home_z_clearance() -> dict[str, Any]:
    clearance = _get_home_z_clearance()
    feed_rate = _get_home_z_feed_rate()
    if not _is_z_axis_enabled():
        return _z_axis_disabled_report(
            "home_z_clearance",
            clearance=clearance,
            delta=0.0,
            feed_rate=feed_rate,
        )

    clearance_delta = -_get_limit_toward_zero_sign("Z") * clearance
    if clearance <= 1e-9:
        return {
            "axis": "z",
            "action": "home_z_clearance",
            "skipped": True,
            "clearance": 0.0,
            "delta": 0.0,
            "feed_rate": feed_rate,
            "results": [],
        }

    return {
        "axis": "z",
        "action": "home_z_clearance",
        "skipped": False,
        "clearance": clearance,
        "delta": clearance_delta,
        "feed_rate": feed_rate,
        "results": _run_grbl_commands(
            [
                ("G21", True),
                ("G91", True),
                (f"G1 Z{clearance_delta} F{feed_rate}", True),
                ("G90", True),
            ],
            wait_for_idle=True,
        ),
    }


def _home_z_axis(precheck_status: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if not _is_z_axis_enabled():
        return _z_axis_disabled_report(
            "home_z_axis",
            already_at_limit=False,
            stopped_by_limit=False,
            limit_axes=[],
            steps=0,
            distance=0.0,
            step_reports=[],
        )

    status = precheck_status or _read_homing_limit_precheck()
    if (status.get("limits") or {}).get("z"):
        return {
            "axis": "z",
            "already_at_limit": True,
            "stopped_by_limit": True,
            "limit_axes": ["z"],
            "status": status,
            "steps": 0,
            "distance": 0.0,
            "step_reports": [],
        }

    feed_rate = _get_home_z_feed_rate()
    step_size = _get_home_z_step()
    search_distance = _get_home_z_search_distance()
    if step_size <= 1e-9:
        raise HTTPException(status_code=400, detail="Z homing step must be greater than 0.")

    home_direction = _get_limit_toward_zero_sign("Z")
    max_steps = max(1, math.ceil(search_distance / step_size))
    moved_distance = 0.0
    step_reports = []

    for step_index in range(1, max_steps + 1):
        remaining_distance = max(0.0, search_distance - moved_distance)
        if remaining_distance <= 1e-9:
            break

        delta_z = home_direction * min(step_size, remaining_distance)
        results = _run_grbl_commands(
            [
                ("G21", True),
                ("G91", True),
                (f"G1 Z{delta_z} F{feed_rate}", True),
                ("G90", True),
            ],
            wait_for_idle=True,
            precheck_limit_axes={"z"},
            observe_limit_axes={"z"},
            require_limit_precheck=True,
        )
        limit_axes = _extract_limit_axes_from_results(results)
        moved_distance += abs(delta_z)
        step_report = {
            "step": step_index,
            "delta": delta_z,
            "distance": moved_distance,
            "limit_axes": sorted(limit_axes),
            "results": results,
        }
        step_reports.append(step_report)

        if "z" in limit_axes:
            return {
                "axis": "z",
                "already_at_limit": False,
                "stopped_by_limit": True,
                "limit_axes": sorted(limit_axes),
                "feed_rate": feed_rate,
                "direction": home_direction,
                "step_size": step_size,
                "steps": step_index,
                "distance": moved_distance,
                "step_reports": step_reports,
            }

    try:
        _run_grbl_commands([("G90", True)])
    except HTTPException:
        pass

    raise HTTPException(
        status_code=504,
        detail=f"Z homing failed: Z limit was not reached within {search_distance} mm.",
    )


def _zero_work_position(include_z: bool) -> Any:
    command = "G10 L20 P1 X0 Y0 Z0" if include_z else "G10 L20 P1 X0 Y0"
    try:
        return _run_grbl_commands(
            [
                (command, True),
                ("G90", True),
            ]
        )
    except HTTPException as exc:
        return {"error": exc.detail}


def home_xy_to_limits() -> dict[str, Any]:
    _set_arm_unhomed()
    axis_reports = []

    unlock_result = _unlock_grbl_if_needed()

    nc_limit_setting = ensure_nc_limit_pin_setting()
    limit_precheck = _read_homing_limit_precheck()

    for axis in _get_home_xy_axis_order():
        axis_reports.append(_home_xy_axis(axis, precheck_status=limit_precheck))

    _set_arm_homed_zero()
    zero_result = _zero_work_position(include_z=False)

    return {
        "action": "home_xy_to_limits",
        "homed": True,
        "position": {"x": 0.0, "y": 0.0},
        "axis_reports": axis_reports,
        "limit_precheck": limit_precheck,
        "unlock_result": unlock_result,
        "nc_limit_setting": nc_limit_setting,
        "zero_result": zero_result,
    }


def home_axes_to_limits() -> dict[str, Any]:
    _set_arm_unhomed()
    axis_reports = []
    z_axis_enabled = _is_z_axis_enabled()

    unlock_result = _unlock_grbl_if_needed()
    nc_limit_setting = ensure_nc_limit_pin_setting()
    limit_precheck = _read_homing_limit_precheck()
    z_clearance = _home_z_clearance()

    for axis in _get_home_xy_axis_order():
        axis_reports.append(_home_xy_axis(axis, precheck_status=limit_precheck))

    _set_arm_homed_zero()
    z_limit_precheck = _read_homing_limit_precheck() if z_axis_enabled else None
    z_report = _home_z_axis(precheck_status=z_limit_precheck)
    zero_result = _zero_work_position(include_z=z_axis_enabled)

    return {
        "action": "home_axes_to_limits",
        "homed": True,
        "position": {"x": 0.0, "y": 0.0, "z": 0.0 if z_axis_enabled else None},
        "z_axis_enabled": z_axis_enabled,
        "sequence": ["z_clearance", "home_xy", "home_z"],
        "limit_precheck": limit_precheck,
        "z_clearance": z_clearance,
        "axis_reports": axis_reports,
        "z_limit_precheck": z_limit_precheck,
        "z_report": z_report,
        "unlock_result": unlock_result,
        "nc_limit_setting": nc_limit_setting,
        "zero_result": zero_result,
    }


def _parse_sequence(raw_sequence: str) -> list[str]:
    parts = re.split(r"[|\n;]+", raw_sequence)
    return [part.strip() for part in parts if part.strip()]


def _feed_rate() -> int:
    return int(os.getenv("APP_GRBL_FEED_RATE", "3000"))


def move_to_front_of_phone() -> dict[str, Any]:
    x = float(os.getenv("APP_GRBL_FRONT_X", "50.0"))
    y = float(os.getenv("APP_GRBL_FRONT_Y", "100.0"))
    target = _clamp_xy_target_to_soft_limits(x, y)
    feed_rate = _feed_rate()
    return {
        "action": "move_to_front",
        "bounded_by_soft_limit": target["bounded"],
        "requested_target": target["requested"],
        "target": {"x": target["x"], "y": target["y"]},
        "soft_limits": target["soft_limits"],
        "results": [
            send_grbl("G21"),
            send_grbl("G90"),
            send_grbl(f"G1 X{target['x']} Y{target['y']} F{feed_rate}"),
        ],
    }


def move_to_back_of_phone() -> dict[str, Any]:
    x = float(os.getenv("APP_GRBL_BACK_X", "50.0"))
    y = float(os.getenv("APP_GRBL_BACK_Y", "20.0"))
    target = _clamp_xy_target_to_soft_limits(x, y)
    feed_rate = _feed_rate()
    return {
        "action": "move_to_back",
        "bounded_by_soft_limit": target["bounded"],
        "requested_target": target["requested"],
        "target": {"x": target["x"], "y": target["y"]},
        "soft_limits": target["soft_limits"],
        "results": [
            send_grbl("G21"),
            send_grbl("G90"),
            send_grbl(f"G1 X{target['x']} Y{target['y']} F{feed_rate}"),
        ],
    }


def _move_z_absolute(target_z: float, action: str) -> dict[str, Any]:
    if not _is_z_axis_enabled():
        return _z_axis_disabled_report(action, target_z=target_z)

    feed_rate = _feed_rate()
    return {
        "action": action,
        "results": _run_grbl_commands(
            [
                ("G21", True),
                ("G90", True),
                (f"G1 Z{target_z} F{feed_rate}", True),
            ]
        ),
    }


def _jog_z(delta_z: float, action: str) -> dict[str, Any]:
    if not _is_z_axis_enabled():
        return _z_axis_disabled_report(action, delta=delta_z)

    feed_rate = _get_manual_z_feed_rate()
    return {
        "action": action,
        "results": _run_grbl_commands(
            [
                ("G21", True),
                ("G91", True),
                (f"G1 Z{delta_z} F{feed_rate}", True),
                ("G90", True),
            ],
            wait_for_idle=True,
        ),
    }


def _format_xy_jog_command(delta_x: float, delta_y: float, feed_rate: int) -> str:
    axis_parts = []

    if abs(delta_x) > 1e-9:
        axis_parts.append(f"X{delta_x}")
    if abs(delta_y) > 1e-9:
        axis_parts.append(f"Y{delta_y}")

    if not axis_parts:
        raise HTTPException(status_code=400, detail="At least one XY jog delta must be non-zero.")

    return f"G1 {' '.join(axis_parts)} F{feed_rate}"


def _jog_xy(delta_x: float, delta_y: float, action: str) -> dict[str, Any]:
    feed_rate = _get_manual_xy_feed_rate()
    bounded_delta = _clamp_xy_delta_to_soft_limits(delta_x, delta_y)
    adjusted_delta_x = bounded_delta["delta_x"]
    adjusted_delta_y = bounded_delta["delta_y"]

    if bounded_delta["skipped"]:
        return {
            "action": action,
            "feed_rate": feed_rate,
            "requested_delta": {"x": delta_x, "y": delta_y},
            "applied_delta": {"x": 0.0, "y": 0.0},
            "bounded_by_soft_limit": bounded_delta["bounded"],
            "skipped": True,
            "stopped_by_limit": False,
            "limit_axes": [],
            "soft_limits": bounded_delta["soft_limits"],
            "position": _status_position(None),
            "results": [],
        }

    limit_stop_axes = _limit_stop_axes_for_xy_delta(adjusted_delta_x, adjusted_delta_y)
    moving_axes = _moving_axes_for_xy_delta(adjusted_delta_x, adjusted_delta_y)
    results = _run_grbl_commands(
        [
            ("G21", True),
            ("G91", True),
            (_format_xy_jog_command(adjusted_delta_x, adjusted_delta_y, feed_rate), True),
        ],
        wait_for_idle=True,
        precheck_limit_axes=limit_stop_axes,
        limit_stop_axes=limit_stop_axes,
        observe_limit_axes=moving_axes,
    )

    limit_axes = _extract_limit_axes_from_results(results)
    stopped_by_limit = bool(limit_axes)

    _apply_xy_delta_to_tracked_position(
        0.0 if stopped_by_limit else adjusted_delta_x,
        0.0 if stopped_by_limit else adjusted_delta_y,
        limit_axes,
    )

    return {
        "action": action,
        "feed_rate": feed_rate,
        "requested_delta": {"x": delta_x, "y": delta_y},
        "applied_delta": {"x": adjusted_delta_x, "y": adjusted_delta_y},
        "bounded_by_soft_limit": bounded_delta["bounded"],
        "skipped": False,
        "stopped_by_limit": stopped_by_limit,
        "limit_axes": sorted(limit_axes),
        "soft_limits": bounded_delta["soft_limits"],
        "position": _status_position(None),
        "results": results,
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
    target = _clamp_xy_target_to_soft_limits(x, y)
    slow_feed = max(200, _feed_rate() // 6)
    threshold = _get_distance_threshold()
    send_grbl("G90", wait_for_ok=True)
    send_grbl(f"G1 X{target['x']} Y{target['y']} F{slow_feed}", wait_for_ok=False)
    for _ in range(200):
        result = _machine_svc.read_distance()
        distance = result.get("distance_cm", -1)
        if 0 < distance <= threshold:
            feed_hold()
            return {
                "action": action,
                "stopped": True,
                "distance_cm": distance,
                "bounded_by_soft_limit": target["bounded"],
                "requested_target": target["requested"],
                "target": {"x": target["x"], "y": target["y"]},
                "soft_limits": target["soft_limits"],
            }
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

    with _GRBL_SERIAL_LOCK:
        try:
            ser, startup_lines = _ensure_grbl_serial()
            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()

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
        except HTTPException as exc:
            if exc.status_code >= 500:
                _close_grbl_serial_locked()
            raise
        except Exception as exc:
            _close_grbl_serial_locked()
            raise HTTPException(status_code=500, detail=f"Failed to talk to GRBL on {port}: {exc}") from exc
