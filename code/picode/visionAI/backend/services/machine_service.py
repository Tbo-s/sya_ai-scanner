import os
import re
import threading
import time
from typing import Callable, Optional

from fastapi import HTTPException
import serial  # type: ignore


GATE_POSITION_PATTERN = re.compile(r"^(?:ACK:)?GATE_POS=(UP|DOWN|UNKNOWN)$")
STATUS_LINE_PATTERN = re.compile(r"^(?:ACK:STATUS,)?gateState=.*\btrayInSw=\d+\s*$")
_LEONARDO_SERIAL_LOCK = threading.RLock()
_LEONARDO_SERIAL: Optional[serial.Serial] = None
_LEONARDO_SERIAL_PORT = ""
_LEONARDO_SERIAL_BAUD = 0
_WRIST_ANGLE_CACHE = {1: int(os.getenv("APP_WRIST1_HOME_ANGLE", "93")), 2: 90}
_LAST_STATUS_VALUES: dict[str, str] = {}
_LAST_STATUS_RESPONSE: list[str] = []
_LAST_STATUS_AT = 0.0


def _get_leonardo_port() -> str:
    return os.getenv("APP_LEONARDO_PORT", os.getenv("APP_ARDUINO_PORT", "/dev/ttyACM0"))


def _get_leonardo_baud() -> int:
    return int(os.getenv("APP_LEONARDO_BAUD", "115200"))


def _get_leonardo_read_timeout_s() -> float:
    return max(0.1, float(os.getenv("APP_LEONARDO_READ_TIMEOUT_S", "0.8")))


def _get_leonardo_open_delay_s() -> float:
    return max(0.0, float(os.getenv("APP_LEONARDO_OPEN_DELAY_S", "0.35")))


def _get_leonardo_command_open_delay_s() -> float:
    return max(0.0, float(os.getenv("APP_LEONARDO_COMMAND_OPEN_DELAY_S", "0.8")))


def _get_leonardo_post_write_hold_s() -> float:
    return max(0.0, float(os.getenv("APP_LEONARDO_POST_WRITE_HOLD_S", "0.25")))


def _get_leonardo_write_retry_delay_s() -> float:
    return max(0.0, float(os.getenv("APP_LEONARDO_WRITE_RETRY_DELAY_S", "0.35")))


def _get_leonardo_write_timeout_s() -> float:
    return max(0.1, float(os.getenv("APP_LEONARDO_WRITE_TIMEOUT_S", "1.0")))


def _hold_leonardo_control_lines_inactive() -> bool:
    return os.getenv("APP_LEONARDO_CONTROL_LINES_INACTIVE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _use_persistent_leonardo_serial() -> bool:
    return os.getenv("APP_LEONARDO_PERSISTENT_SERIAL", "0").strip().lower() in {"1", "true", "yes", "on"}


def _get_leonardo_status_retries() -> int:
    return max(1, int(os.getenv("APP_LEONARDO_STATUS_RETRIES", "3")))


def _get_leonardo_status_retry_delay_s() -> float:
    return max(0.0, float(os.getenv("APP_LEONARDO_STATUS_RETRY_DELAY_S", "0.25")))


def _get_leonardo_poll_status_timeout_s() -> float:
    return max(0.05, float(os.getenv("APP_LEONARDO_POLL_STATUS_TIMEOUT_S", "0.1")))


def _get_wrist_dwell_ms() -> int:
    return int(os.getenv("APP_WRIST_DWELL_MS", "600"))


def _get_wrist_smooth_step_deg() -> int:
    return max(1, int(os.getenv("APP_WRIST_SMOOTH_STEP_DEG", "2")))


def _get_wrist_smooth_delay_ms() -> int:
    return max(0, int(os.getenv("APP_WRIST_SMOOTH_DELAY_MS", "25")))


def _get_wrist_min_angle(wrist_index: Optional[int] = None) -> int:
    if wrist_index in (1, 2):
        specific = os.getenv(f"APP_WRIST{wrist_index}_MIN_ANGLE")
        if specific is not None:
            return int(specific)
    return int(os.getenv("APP_WRIST_MIN_ANGLE", "-5"))


def _get_wrist_max_angle(wrist_index: Optional[int] = None) -> int:
    if wrist_index in (1, 2):
        specific = os.getenv(f"APP_WRIST{wrist_index}_MAX_ANGLE")
        if specific is not None:
            return int(specific)
    return int(os.getenv("APP_WRIST_MAX_ANGLE", "182"))


def _clamp_wrist_angle(angle: int, wrist_index: Optional[int] = None) -> int:
    min_angle = _get_wrist_min_angle(wrist_index)
    max_angle = _get_wrist_max_angle(wrist_index)
    if min_angle > max_angle:
        min_angle, max_angle = max_angle, min_angle
    return max(min_angle, min(max_angle, int(angle)))


def wrist_min_angle(wrist_index: Optional[int] = None) -> int:
    return min(_get_wrist_min_angle(wrist_index), _get_wrist_max_angle(wrist_index))


def wrist_max_angle(wrist_index: Optional[int] = None) -> int:
    return max(_get_wrist_min_angle(wrist_index), _get_wrist_max_angle(wrist_index))


def wrist1_home_angle() -> int:
    return _clamp_wrist_angle(int(os.getenv("APP_WRIST1_HOME_ANGLE", "93")), 1)


def _close_leonardo_serial():
    global _LEONARDO_SERIAL, _LEONARDO_SERIAL_PORT, _LEONARDO_SERIAL_BAUD
    if _LEONARDO_SERIAL is not None:
        try:
            _LEONARDO_SERIAL.close()
        except Exception:
            pass
    _LEONARDO_SERIAL = None
    _LEONARDO_SERIAL_PORT = ""
    _LEONARDO_SERIAL_BAUD = 0


def _reset_serial_buffers(ser: serial.Serial):
    if hasattr(ser, "reset_input_buffer"):
        ser.reset_input_buffer()
    if hasattr(ser, "reset_output_buffer"):
        try:
            ser.reset_output_buffer()
        except Exception:
            pass


def _write_serial_line(ser: serial.Serial, line: str):
    ser.write((line.strip() + "\n").encode("ascii", errors="ignore"))


def _set_serial_lines_inactive(ser: serial.Serial):
    for line_signal in ("dtr", "rts"):
        if hasattr(ser, line_signal):
            try:
                setattr(ser, line_signal, False)
            except Exception:
                pass


def _set_serial_lines_active(ser: serial.Serial):
    for line_signal in ("dtr", "rts"):
        if hasattr(ser, line_signal):
            try:
                setattr(ser, line_signal, True)
            except Exception:
                pass


def _is_serial_write_timeout(exc: Exception) -> bool:
    if isinstance(exc, serial.SerialTimeoutException):
        return True
    return "write timeout" in str(exc).strip().lower()


def _open_leonardo_serial(port: str, baudrate: int) -> serial.Serial:
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baudrate
    ser.timeout = 0.2
    ser.write_timeout = _get_leonardo_write_timeout_s()
    if _hold_leonardo_control_lines_inactive():
        _set_serial_lines_inactive(ser)
    ser.open()
    if _hold_leonardo_control_lines_inactive():
        _set_serial_lines_inactive(ser)
    else:
        _set_serial_lines_active(ser)
    _reset_serial_buffers(ser)
    return ser


def _get_leonardo_serial() -> serial.Serial:
    global _LEONARDO_SERIAL, _LEONARDO_SERIAL_PORT, _LEONARDO_SERIAL_BAUD

    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    if (
        _LEONARDO_SERIAL is not None
        and getattr(_LEONARDO_SERIAL, "is_open", True)
        and _LEONARDO_SERIAL_PORT == port
        and _LEONARDO_SERIAL_BAUD == baudrate
    ):
        return _LEONARDO_SERIAL

    _close_leonardo_serial()
    _LEONARDO_SERIAL = _open_leonardo_serial(port, baudrate)
    _LEONARDO_SERIAL_PORT = port
    _LEONARDO_SERIAL_BAUD = baudrate

    open_delay_s = _get_leonardo_open_delay_s()
    if open_delay_s > 0:
        time.sleep(open_delay_s)

    return _LEONARDO_SERIAL


def warm_up() -> dict:
    if not _use_persistent_leonardo_serial():
        return {"ok": True, "skipped": True, "reason": "persistent_serial_disabled"}

    port = _get_leonardo_port()
    try:
        with _LEONARDO_SERIAL_LOCK:
            _get_leonardo_serial()
        return {"ok": True, "port": port}
    except Exception as exc:
        _close_leonardo_serial()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to warm Leonardo serial device on {port}: {exc}",
        ) from exc


def _send_line(line: str):
    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            with _LEONARDO_SERIAL_LOCK:
                if _use_persistent_leonardo_serial():
                    ser = _get_leonardo_serial()
                    _write_serial_line(ser, line)
                    hold_s = _get_leonardo_post_write_hold_s()
                    if hold_s > 0:
                        time.sleep(hold_s)
                    return

                ser = _open_leonardo_serial(port, baudrate)
                try:
                    open_delay_s = _get_leonardo_command_open_delay_s()
                    if open_delay_s > 0:
                        time.sleep(open_delay_s)
                    _write_serial_line(ser, line)
                    hold_s = _get_leonardo_post_write_hold_s()
                    if hold_s > 0:
                        time.sleep(hold_s)
                    return
                finally:
                    ser.close()
        except Exception as exc:
            last_exc = exc
            _close_leonardo_serial()
            if attempt == 0 and _is_serial_write_timeout(exc):
                retry_delay_s = _get_leonardo_write_retry_delay_s()
                if retry_delay_s > 0:
                    time.sleep(retry_delay_s)
                continue
            raise HTTPException(
                status_code=500,
                detail=f"Failed to talk to serial device on {port}: {exc}",
            ) from exc

    raise HTTPException(
        status_code=500,
        detail=f"Failed to talk to serial device on {port}: {last_exc or 'unknown error'}",
    )


def _send_with_response(
    command: str,
    timeout_s: Optional[float] = None,
    stop_when: Optional[Callable[[str], bool]] = None,
    open_delay_s: Optional[float] = None,
) -> list[str]:
    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    read_timeout_s = timeout_s if timeout_s is not None else _get_leonardo_read_timeout_s()
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            with _LEONARDO_SERIAL_LOCK:
                if _use_persistent_leonardo_serial():
                    ser = _get_leonardo_serial()
                    if hasattr(ser, "reset_input_buffer"):
                        ser.reset_input_buffer()
                    _write_serial_line(ser, command)
                    started_at = time.time()
                    lines: list[str] = []
                    while time.time() - started_at < read_timeout_s:
                        raw = ser.readline()
                        if not raw:
                            continue
                        text = raw.decode("utf-8", errors="ignore").strip()
                        if text:
                            lines.append(text)
                            if stop_when is not None and stop_when(text):
                                return lines
                    return lines

                ser = _open_leonardo_serial(port, baudrate)
                try:
                    delay_s = _get_leonardo_open_delay_s() if open_delay_s is None else open_delay_s
                    if delay_s > 0:
                        time.sleep(delay_s)
                    if hasattr(ser, "reset_input_buffer"):
                        ser.reset_input_buffer()
                    _write_serial_line(ser, command)
                    started_at = time.time()
                    lines: list[str] = []
                    while time.time() - started_at < read_timeout_s:
                        raw = ser.readline()
                        if not raw:
                            continue
                        text = raw.decode("utf-8", errors="ignore").strip()
                        if text:
                            lines.append(text)
                            if stop_when is not None and stop_when(text):
                                return lines
                    return lines
                finally:
                    ser.close()
        except Exception as exc:
            last_exc = exc
            _close_leonardo_serial()
            if attempt == 0 and _is_serial_write_timeout(exc):
                retry_delay_s = _get_leonardo_write_retry_delay_s()
                if retry_delay_s > 0:
                    time.sleep(retry_delay_s)
                continue
            raise HTTPException(
                status_code=500,
                detail=f"Failed to talk to serial device on {port}: {exc}",
            ) from exc

    raise HTTPException(
        status_code=500,
        detail=f"Failed to talk to serial device on {port}: {last_exc or 'unknown error'}",
    )


def _extract_gate_position(lines: list[str]) -> Optional[str]:
    for line in reversed(lines):
        match = GATE_POSITION_PATTERN.match(line.strip())
        if match:
            return match.group(1)
    return None


def _status_payload_from_line(line: str) -> Optional[str]:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("ACK:STATUS,"):
        return stripped[len("ACK:STATUS,") :]
    if STATUS_LINE_PATTERN.match(stripped):
        return stripped
    return None


def _extract_status_line(lines: list[str]) -> Optional[str]:
    for line in reversed(lines):
        payload = _status_payload_from_line(line)
        if payload is not None:
            return payload
    return None


def _line_matches_pattern(pattern: re.Pattern, line: str) -> bool:
    return pattern.match(line.strip()) is not None


def _parse_status_values(status_line: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for part in status_line.split(","):
        chunk = part.strip()
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _normalize_status_values(values: dict[str, str]) -> dict[str, str]:
    normalized = dict(values)
    for wrist_index in (1, 2):
        legacy_key = f"wrist{wrist_index}"
        logical_key = f"wrist{wrist_index}_logical"
        physical_key = f"wrist{wrist_index}_physical"

        if logical_key in normalized and legacy_key not in normalized:
            normalized[legacy_key] = normalized[logical_key]
        elif legacy_key in normalized and logical_key not in normalized:
            normalized[logical_key] = normalized[legacy_key]

        if physical_key not in normalized and legacy_key in normalized:
            normalized[physical_key] = normalized[legacy_key]

    return normalized


def _update_cached_state(values: dict[str, str]):
    for wrist_index in (1, 2):
        try:
            _WRIST_ANGLE_CACHE[wrist_index] = _clamp_wrist_angle(
                int(values.get(f"wrist{wrist_index}", _WRIST_ANGLE_CACHE[wrist_index]))
                ,
                wrist_index,
            )
        except (TypeError, ValueError):
            pass


def _cache_status_values(values: dict[str, str], lines: list[str]):
    global _LAST_STATUS_VALUES, _LAST_STATUS_RESPONSE, _LAST_STATUS_AT
    _LAST_STATUS_VALUES = dict(values)
    _LAST_STATUS_RESPONSE = list(lines[-20:])
    _LAST_STATUS_AT = time.time()


def _cached_status_payload(*, lines: Optional[list[str]] = None, lock_busy: bool = False, stale: bool = False) -> dict:
    age_ms: Optional[int] = None
    if _LAST_STATUS_AT > 0:
        age_ms = max(0, int((time.time() - _LAST_STATUS_AT) * 1000))
    return {
        "command": "STATUS",
        "found": bool(_LAST_STATUS_VALUES),
        "status": dict(_LAST_STATUS_VALUES),
        "response": list(lines if lines is not None else _LAST_STATUS_RESPONSE),
        "cached": bool(_LAST_STATUS_VALUES),
        "lock_busy": lock_busy,
        "stale": stale,
        "cache_age_ms": age_ms,
    }


def _format_status_attempts_for_error(attempts: list[dict]) -> str:
    if not attempts:
        return "no response"

    formatted_attempts: list[str] = []
    for attempt in attempts:
        response = attempt.get("response", [])
        response_preview = " | ".join(response[-8:]) if response else "no response"
        formatted_attempts.append(f"attempt {attempt.get('attempt')}: {response_preview}")
    return "; ".join(formatted_attempts)


def _derive_tray_position_from_status(values: dict[str, str]) -> str:
    tray_out_sw = values.get("trayOutSw")
    tray_in_sw = values.get("trayInSw")
    out_pressed = tray_out_sw == "1"
    in_pressed = tray_in_sw == "1"
    if out_pressed and not in_pressed:
        return "OUT"
    if in_pressed and not out_pressed:
        return "IN"
    return "UNKNOWN"


def _contains_token(lines: list[str], token: str) -> bool:
    return any(token in line for line in lines)


def _contains_any_token(lines: list[str], tokens: tuple[str, ...]) -> bool:
    return any(any(token in line for token in tokens) for line in lines)


def _flatten_command_responses(results: list[dict]) -> list[str]:
    lines: list[str] = []
    for result in results:
        lines.extend(result.get("response", []))
    return lines


def _send_sequence_with_response(
    commands: list[str],
    timeout_s: Optional[float] = None,
    inter_command_delay_s: float = 0.0,
) -> list[dict]:
    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    read_timeout_s = timeout_s if timeout_s is not None else _get_leonardo_read_timeout_s()
    try:
        with _LEONARDO_SERIAL_LOCK:
            if _use_persistent_leonardo_serial():
                ser = _get_leonardo_serial()
                if hasattr(ser, "reset_input_buffer"):
                    ser.reset_input_buffer()

                results: list[dict] = []
                for index, command in enumerate(commands):
                    _write_serial_line(ser, command)
                    started_at = time.time()
                    lines: list[str] = []
                    while time.time() - started_at < read_timeout_s:
                        raw = ser.readline()
                        if not raw:
                            continue
                        text = raw.decode("utf-8", errors="ignore").strip()
                        if text:
                            lines.append(text)
                            break
                    results.append({"command": command, "response": lines})
                    if inter_command_delay_s > 0 and index < len(commands) - 1:
                        time.sleep(inter_command_delay_s)
                return results

            ser = _open_leonardo_serial(port, baudrate)
            try:
                open_delay_s = _get_leonardo_open_delay_s()
                if open_delay_s > 0:
                    time.sleep(open_delay_s)
                if hasattr(ser, "reset_input_buffer"):
                    ser.reset_input_buffer()

                results: list[dict] = []
                for index, command in enumerate(commands):
                    _write_serial_line(ser, command)
                    started_at = time.time()
                    lines: list[str] = []
                    while time.time() - started_at < read_timeout_s:
                        raw = ser.readline()
                        if not raw:
                            continue
                        text = raw.decode("utf-8", errors="ignore").strip()
                        if text:
                            lines.append(text)
                            break
                    results.append({"command": command, "response": lines})
                    if inter_command_delay_s > 0 and index < len(commands) - 1:
                        time.sleep(inter_command_delay_s)
                return results
            finally:
                ser.close()
    except Exception as exc:
        _close_leonardo_serial()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to serial device on {port}: {exc}",
        ) from exc


def _send_command_until_token(
    ser: serial.Serial,
    command: str,
    expected_tokens: tuple[str, ...],
    timeout_s: Optional[float] = None,
) -> list[str]:
    read_timeout_s = timeout_s if timeout_s is not None else _get_leonardo_read_timeout_s()
    _write_serial_line(ser, command)
    started_at = time.time()
    lines: list[str] = []
    while time.time() - started_at < read_timeout_s:
        raw = ser.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            continue
        lines.append(text)
        if any(token in text for token in expected_tokens):
            return lines
    return lines


def _get_status_values(
    *,
    timeout_s: Optional[float] = None,
    retries: Optional[int] = None,
    raise_on_missing: bool = True,
) -> tuple[dict[str, str], list[str]]:
    with _LEONARDO_SERIAL_LOCK:
        attempts: list[dict] = []
        all_lines: list[str] = []
        max_retries = retries if retries is not None else _get_leonardo_status_retries()

        for attempt in range(1, max_retries + 1):
            lines = _send_with_response(
                "STATUS",
                timeout_s=timeout_s,
                stop_when=lambda line: _line_matches_pattern(STATUS_LINE_PATTERN, line),
            )
            attempts.append({"attempt": attempt, "response": lines})
            all_lines.extend(lines)

            status_line = _extract_status_line(lines)
            if status_line:
                values = _normalize_status_values(_parse_status_values(status_line))
                _update_cached_state(values)
                _cache_status_values(values, all_lines)
                return values, all_lines

            if attempt < max_retries:
                delay_s = _get_leonardo_status_retry_delay_s()
                if delay_s > 0:
                    time.sleep(delay_s)

    if not raise_on_missing:
        return {}, all_lines

    raise HTTPException(
        status_code=504,
        detail=(
            f"STATUS did not return a parseable status line after {max_retries} attempt(s). "
            "Expected a line like 'gateState=..., trayInSw=0/1'. "
            f"Responses: {_format_status_attempts_for_error(attempts)}"
        ),
    )


def _get_status_int(values: dict[str, str], key: str, default: int) -> int:
    try:
        return int(values.get(key, default))
    except (TypeError, ValueError):
        return default


def _require_done(command: str, ack: bool, response: list[str]) -> dict:
    if not ack:
        raise HTTPException(status_code=504, detail=f"{command} did not acknowledge before timeout.")
    return {"command": command, "sent": True, "ack": True, "response": response}


def _wrist_expected_tokens(wrist_index: int, angle: int) -> tuple[str, ...]:
    return (
        f"WRIST{wrist_index}_DONE:{angle}",
        f"ACK:WRIST{wrist_index}_ANGLE={angle}",
    )


def _get_wrist_current_angle(status_key: str) -> Optional[int]:
    try:
        values, _ = _get_status_values()
        return _get_status_int(values, status_key, 90)
    except HTTPException:
        return None


def open_gate() -> dict:
    _send_line("GATE_OPEN")
    return {"command": "GATE_OPEN", "sent": True}


def close_gate() -> dict:
    _send_line("GATE_CLOSE")
    return {"command": "GATE_CLOSE", "sent": True}


def tray_out() -> dict:
    _send_line("TRAY_OUT")
    return {"command": "TRAY_OUT", "sent": True}


def tray_in() -> dict:
    _send_line("TRAY_IN")
    return {"command": "TRAY_IN", "sent": True}


def tray_stop() -> dict:
    _send_line("TRAY_STOP")
    return {"command": "TRAY_STOP", "sent": True}


def get_gate_position() -> dict:
    lines = _send_with_response(
        "GATE_POS",
        stop_when=lambda line: _line_matches_pattern(GATE_POSITION_PATTERN, line),
    )
    position = _extract_gate_position(lines)
    return {
        "command": "GATE_POS",
        "position": position,
        "found": position is not None,
        "source": "gate_pos",
        "response": lines,
    }


def get_tray_position() -> dict:
    lines = _send_with_response(
        "STATUS",
        stop_when=lambda line: _line_matches_pattern(STATUS_LINE_PATTERN, line),
    )
    status_line = _extract_status_line(lines)
    if not status_line:
        return {
            "command": "STATUS",
            "position": None,
            "found": False,
            "source": "status",
            "response": lines,
        }
    values = _parse_status_values(status_line)
    position = _derive_tray_position_from_status(values)
    return {
        "command": "STATUS",
        "position": position,
        "found": True,
        "source": "status",
        "status": values,
        "response": lines,
    }


def get_status() -> dict:
    acquired = _LEONARDO_SERIAL_LOCK.acquire(blocking=False)
    if not acquired:
        return _cached_status_payload(lock_busy=True, stale=True)

    try:
        values, lines = _get_status_values(
            timeout_s=_get_leonardo_poll_status_timeout_s(),
            retries=1,
            raise_on_missing=False,
        )
    finally:
        _LEONARDO_SERIAL_LOCK.release()

    if values:
        return {
            "command": "STATUS",
            "found": True,
            "status": values,
            "response": lines,
            "cached": False,
            "lock_busy": False,
            "stale": False,
            "cache_age_ms": 0,
        }

    if _LAST_STATUS_VALUES:
        return _cached_status_payload(lines=lines, stale=True)

    return {
        "command": "STATUS",
        "found": False,
        "status": {},
        "response": lines,
        "cached": False,
        "lock_busy": False,
        "stale": True,
        "cache_age_ms": None,
    }


def home_machine() -> dict:
    return {"ok": True, "actions": [tray_in(), close_gate()]}


def emergency_stop() -> dict:
    _send_line("STOP_ALL")
    return {"command": "STOP_ALL", "sent": True}


def vacuum_on(raise_on_no_ack: bool = True) -> dict:
    results = _send_sequence_with_response(["VAC_ALL_ON", "VALVE_ALL_ON"], timeout_s=0.4)
    lines = _flatten_command_responses(results)
    done = _contains_any_token(lines, ("VAC_ALL_ON_DONE", "ACK:VAC_ALL_ON")) and _contains_any_token(
        lines, ("VALVE_ALL_ON_DONE", "ACK:VALVE_ALL_ON")
    )
    if raise_on_no_ack:
        return _require_done("VAC_ALL_ON+VALVE_ALL_ON", done, lines) | {"results": results}
    return {"command": "VAC_ALL_ON+VALVE_ALL_ON", "sent": True, "ack": done, "response": lines, "results": results}


def vacuum_off(raise_on_no_ack: bool = True) -> dict:
    results = _send_sequence_with_response(["VAC_ALL_OFF", "VALVE_ALL_OFF"], timeout_s=0.4)
    lines = _flatten_command_responses(results)
    done = _contains_any_token(lines, ("VAC_ALL_OFF_DONE", "ACK:VAC_ALL_OFF")) and _contains_any_token(
        lines, ("VALVE_ALL_OFF_DONE", "ACK:VALVE_ALL_OFF")
    )
    if raise_on_no_ack:
        return _require_done("VAC_ALL_OFF+VALVE_ALL_OFF", done, lines) | {"results": results}
    return {"command": "VAC_ALL_OFF+VALVE_ALL_OFF", "sent": True, "ack": done, "response": lines, "results": results}


def _set_binary_output(
    *,
    command_on: str,
    command_off: str,
    done_on: str,
    done_off: str,
    enabled: bool,
    raise_on_no_ack: bool = True,
) -> dict:
    command = command_on if enabled else command_off
    expected = done_on if enabled else done_off
    _send_line(command)
    return {
        "command": command,
        "sent": True,
        "ack": False,
        "ack_skipped": True,
        "expected": expected,
        "enabled": enabled,
        "response": [],
    }


def set_vacuum1_motor(enabled: bool, raise_on_no_ack: bool = True) -> dict:
    return _set_binary_output(
        command_on="VAC1_ON",
        command_off="VAC1_OFF",
        done_on="VAC1_ON_DONE",
        done_off="VAC1_OFF_DONE",
        enabled=enabled,
        raise_on_no_ack=raise_on_no_ack,
    )


def set_vacuum2_motor(enabled: bool, raise_on_no_ack: bool = True) -> dict:
    return _set_binary_output(
        command_on="VAC2_ON",
        command_off="VAC2_OFF",
        done_on="VAC2_ON_DONE",
        done_off="VAC2_OFF_DONE",
        enabled=enabled,
        raise_on_no_ack=raise_on_no_ack,
    )


def set_valve1(enabled: bool, raise_on_no_ack: bool = True) -> dict:
    return _set_binary_output(
        command_on="VALVE1_ON",
        command_off="VALVE1_OFF",
        done_on="VALVE1_ON_DONE",
        done_off="VALVE1_OFF_DONE",
        enabled=enabled,
        raise_on_no_ack=raise_on_no_ack,
    )


def set_valve2(enabled: bool, raise_on_no_ack: bool = True) -> dict:
    return _set_binary_output(
        command_on="VALVE2_ON",
        command_off="VALVE2_OFF",
        done_on="VALVE2_ON_DONE",
        done_off="VALVE2_OFF_DONE",
        enabled=enabled,
        raise_on_no_ack=raise_on_no_ack,
    )


def set_vacuum1(enabled: bool, raise_on_no_ack: bool = True) -> dict:
    commands = ["VAC1_ON", "VALVE1_ON"] if enabled else ["VAC1_OFF", "VALVE1_OFF"]
    expected = [("VAC1_ON_DONE", "ACK:VAC1_ON"), ("VALVE1_ON_DONE", "ACK:VALVE1_ON")] if enabled else [
        ("VAC1_OFF_DONE", "ACK:VAC1_OFF"),
        ("VALVE1_OFF_DONE", "ACK:VALVE1_OFF"),
    ]
    results = _send_sequence_with_response(commands, timeout_s=0.4)
    lines = _flatten_command_responses(results)
    done = all(_contains_any_token(lines, tokens) for tokens in expected)
    command = "+".join(commands)
    if raise_on_no_ack:
        return _require_done(command, done, lines) | {"enabled": enabled, "results": results}
    return {"command": command, "sent": True, "ack": done, "enabled": enabled, "response": lines, "results": results}


def set_vacuum2(enabled: bool, raise_on_no_ack: bool = True) -> dict:
    commands = ["VAC2_ON", "VALVE2_ON"] if enabled else ["VAC2_OFF", "VALVE2_OFF"]
    expected = [("VAC2_ON_DONE", "ACK:VAC2_ON"), ("VALVE2_ON_DONE", "ACK:VALVE2_ON")] if enabled else [
        ("VAC2_OFF_DONE", "ACK:VAC2_OFF"),
        ("VALVE2_OFF_DONE", "ACK:VALVE2_OFF"),
    ]
    results = _send_sequence_with_response(commands, timeout_s=0.4)
    lines = _flatten_command_responses(results)
    done = all(_contains_any_token(lines, tokens) for tokens in expected)
    command = "+".join(commands)
    if raise_on_no_ack:
        return _require_done(command, done, lines) | {"enabled": enabled, "results": results}
    return {"command": command, "sent": True, "ack": done, "enabled": enabled, "response": lines, "results": results}


def set_wrist1(angle: int) -> dict:
    angle = _clamp_wrist_angle(angle, 1)
    result = _move_wrist_smooth(1, angle, _get_wrist_current_angle("wrist1"))
    _WRIST_ANGLE_CACHE[1] = angle
    return result


def set_wrist2(angle: int) -> dict:
    angle = _clamp_wrist_angle(angle, 2)
    result = _move_wrist_smooth(2, angle, _get_wrist_current_angle("wrist2"))
    _WRIST_ANGLE_CACHE[2] = angle
    return result


def _move_wrist_fast(wrist_index: int, target_angle: int, current_angle: int) -> dict:
    target_angle = _clamp_wrist_angle(target_angle, wrist_index)
    command = f"WRIST{wrist_index}_ANGLE:{target_angle}"
    expected_tokens = _wrist_expected_tokens(wrist_index, target_angle)
    lines = _send_with_response(
        command,
        timeout_s=0.6,
        stop_when=lambda line: any(token in line for token in expected_tokens),
        open_delay_s=_get_leonardo_command_open_delay_s(),
    )
    done = _contains_any_token(lines, expected_tokens)
    _WRIST_ANGLE_CACHE[wrist_index] = target_angle
    return _require_done(command, done, lines) | {
        "angle": target_angle,
        "previous_angle": current_angle,
        "smoothed": False,
    }


def _move_wrist_smooth(wrist_index: int, target_angle: int, current_angle: Optional[int]) -> dict:
    target_angle = _clamp_wrist_angle(target_angle, wrist_index)
    command_prefix = f"WRIST{wrist_index}_ANGLE:"

    if current_angle is None:
        expected_tokens = _wrist_expected_tokens(wrist_index, target_angle)
        lines = _send_with_response(
            f"{command_prefix}{target_angle}",
            stop_when=lambda line: any(token in line for token in expected_tokens),
            open_delay_s=_get_leonardo_command_open_delay_s(),
        )
        done = _contains_any_token(lines, expected_tokens)
        time.sleep(_get_wrist_dwell_ms() / 1000.0)
        return _require_done(f"{command_prefix}{target_angle}", done, lines) | {"angle": target_angle, "smoothed": False}

    current_angle = _clamp_wrist_angle(current_angle, wrist_index)
    if current_angle == target_angle:
        return {
            "command": f"{command_prefix}{target_angle}",
            "sent": True,
            "ack": True,
            "response": [],
            "angle": target_angle,
            "previous_angle": current_angle,
            "smoothed": False,
            "steps": 0,
        }

    step_deg = _get_wrist_smooth_step_deg()
    delay_s = _get_wrist_smooth_delay_ms() / 1000.0
    direction = 1 if target_angle > current_angle else -1

    angles: list[int] = []
    next_angle = current_angle
    while next_angle != target_angle:
        next_angle += direction * step_deg
        if direction > 0:
            next_angle = min(next_angle, target_angle)
        else:
            next_angle = max(next_angle, target_angle)
        angles.append(next_angle)

    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    try:
        with _LEONARDO_SERIAL_LOCK:
            if _use_persistent_leonardo_serial():
                ser = _get_leonardo_serial()
            else:
                ser = _open_leonardo_serial(port, baudrate)

            try:
                if not _use_persistent_leonardo_serial():
                    open_delay_s = _get_leonardo_open_delay_s()
                    if open_delay_s > 0:
                        time.sleep(open_delay_s)
                if hasattr(ser, "reset_input_buffer"):
                    ser.reset_input_buffer()

                results: list[dict] = []
                for index, angle in enumerate(angles):
                    command = f"{command_prefix}{angle}"
                    expected_tokens = _wrist_expected_tokens(wrist_index, angle)
                    lines = _send_command_until_token(ser, command, expected_tokens)
                    done = _contains_any_token(lines, expected_tokens)
                    if not done:
                        raise HTTPException(status_code=504, detail=f"{command} did not acknowledge before timeout.")
                    results.append({"command": command, "response": lines})
                    if delay_s > 0 and index < len(angles) - 1:
                        time.sleep(delay_s)
            finally:
                if not _use_persistent_leonardo_serial():
                    ser.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to serial device on {port}: {exc}",
        ) from exc

    time.sleep(_get_wrist_dwell_ms() / 1000.0)
    return {
        "command": f"{command_prefix}{target_angle}",
        "sent": True,
        "ack": True,
        "response": _flatten_command_responses(results),
        "results": results,
        "angle": target_angle,
        "previous_angle": current_angle,
        "smoothed": len(angles) > 1,
        "steps": len(angles),
    }


def adjust_wrist1(delta: int) -> dict:
    current_angle = _WRIST_ANGLE_CACHE[1]
    target_angle = _clamp_wrist_angle(current_angle + int(delta), 1)
    return _move_wrist_fast(1, target_angle, current_angle) | {"delta": int(delta)}


def adjust_wrist2(delta: int) -> dict:
    current_angle = _WRIST_ANGLE_CACHE[2]
    target_angle = _clamp_wrist_angle(current_angle + int(delta), 2)
    return _move_wrist_fast(2, target_angle, current_angle) | {"delta": int(delta)}


def wrist_home() -> dict:
    return {"wrist1": set_wrist1(wrist1_home_angle()), "wrist2": set_wrist2(0)}


def read_distance() -> dict:
    lines = _send_with_response(
        "DISTANCE_MM",
        stop_when=lambda line: (
            line.startswith("DISTANCE_MM=")
            or line.startswith("DIST=")
            or line.startswith("ACK:DISTANCE_MM=")
        ),
    )
    for line in lines:
        if line.startswith("ACK:DISTANCE_MM="):
            raw_value = line.split("=", 1)[1].strip()
            if raw_value == "ERROR":
                return {"distance_mm": -1, "distance_cm": -1, "found": False, "response": lines}
            try:
                distance_mm = int(raw_value)
                return {
                    "distance_mm": distance_mm,
                    "distance_cm": distance_mm / 10.0,
                    "found": True,
                    "response": lines,
                }
            except ValueError:
                pass
        if line.startswith("DISTANCE_MM="):
            try:
                distance_mm = int(line.split("=", 1)[1].strip())
                return {
                    "distance_mm": distance_mm,
                    "distance_cm": distance_mm / 10.0,
                    "found": True,
                    "response": lines,
                }
            except ValueError:
                pass
        if line.startswith("DIST="):
            try:
                distance_cm = int(line.split("=", 1)[1].strip())
                return {
                    "distance_mm": distance_cm * 10,
                    "distance_cm": distance_cm,
                    "found": True,
                    "response": lines,
                }
            except ValueError:
                pass
    return {"distance_mm": -1, "distance_cm": -1, "found": False, "response": lines}


def read_distance_for_display() -> dict:
    direct = read_distance()
    if direct.get("found"):
        return direct | {"source": "distance_mm"}

    lines = _send_with_response(
        "DISTANCE_STATUS",
        stop_when=lambda line: (
            line.startswith("ACK:DISTANCE_STATUS=")
            or line.startswith("DISTANCE_STATUS=")
        ),
    )

    for line in lines:
        raw_payload = None
        if line.startswith("ACK:DISTANCE_STATUS="):
            raw_payload = line.split("=", 1)[1].strip()
        elif line.startswith("DISTANCE_STATUS="):
            raw_payload = line.split("=", 1)[1].strip()

        if raw_payload is None:
            continue

        values: dict[str, str] = {}
        for part in raw_payload.split(","):
            chunk = part.strip()
            if "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            values[key.strip()] = value.strip()

        def _parse_int_value(key: str, default: int = -1) -> int:
            try:
                return int(values.get(key, str(default)))
            except ValueError:
                return default

        display_mm = _parse_int_value("DISPLAY_MM")
        last_mm = _parse_int_value("LAST_MM")
        valid = _parse_int_value("VALID", 1)
        range_status = _parse_int_value("RANGE_STATUS")

        preferred_mm = display_mm if display_mm >= 0 else last_mm

        if preferred_mm >= 0:
            return {
                "distance_mm": preferred_mm,
                "distance_cm": preferred_mm / 10.0,
                "found": preferred_mm > 0,
                "response": direct.get("response", []) + lines,
                "source": "distance_status",
                "valid": valid == 1,
                "display_mm": display_mm,
                "valid_distance_mm": last_mm,
                "range_status": range_status,
                "stale": valid != 1 or range_status != 0,
            }

    return {
        "distance_mm": -1,
        "distance_cm": -1,
        "found": False,
        "response": direct.get("response", []) + lines,
        "source": "distance_status",
    }


def tray_to_gate_position() -> dict:
    _send_line("TRAY_OUT")
    return {"command": "TRAY_OUT", "sent": True}


def wait_for_gate_done(timeout_s: Optional[float] = None) -> dict:
    if timeout_s is None:
        timeout_s = float(os.getenv("APP_GATE_MOVE_TIMEOUT_S", "10"))
    started = time.time()
    saw_motion = False
    last_values: dict[str, str] = {}
    last_lines: list[str] = []

    while time.time() - started < timeout_s:
        values, lines = _get_status_values(timeout_s=0.25, retries=1, raise_on_missing=False)
        if lines:
            last_lines = lines
        if values:
            last_values = values
            gate_state = _get_status_int(values, "gateState", -1)
            gate_pos = str(values.get("gatePos", "")).upper()
            if gate_state not in {-1, 0}:
                saw_motion = True
            if gate_state == 0 and gate_pos in {"UP", "DOWN"} and (saw_motion or time.time() - started >= 0.25):
                return {"done": True, "status": values, "response": last_lines}
        time.sleep(0.05)

    raise HTTPException(
        status_code=504,
        detail=f"Gate movement timed out. Last status: {last_values or last_lines or 'no response'}",
    )


def wait_for_tray_done(timeout_s: Optional[float] = None) -> dict:
    if timeout_s is None:
        timeout_s = float(os.getenv("APP_TRAY_MOVE_TIMEOUT_S", "10"))
    started = time.time()
    saw_motion = False
    last_values: dict[str, str] = {}
    last_lines: list[str] = []

    while time.time() - started < timeout_s:
        values, lines = _get_status_values(timeout_s=0.25, retries=1, raise_on_missing=False)
        if lines:
            last_lines = lines
        if values:
            last_values = values
            tray_state = _get_status_int(values, "trayState", -1)
            tray_pos = str(values.get("trayPos", "")).upper()
            if tray_state not in {-1, 0}:
                saw_motion = True
            if tray_state == 0 and tray_pos in {"IN", "OUT"} and (saw_motion or time.time() - started >= 0.25):
                return {"done": True, "status": values, "response": last_lines}
        time.sleep(0.05)

    raise HTTPException(
        status_code=504,
        detail=f"Tray movement timed out. Last status: {last_values or last_lines or 'no response'}",
    )
