import os
import re
import time
from typing import Optional

from fastapi import HTTPException
import serial  # type: ignore


GATE_POSITION_PATTERN = re.compile(r"^GATE_POS=(UP|DOWN|UNKNOWN)$")
STATUS_LINE_PATTERN = re.compile(r"^gateState=.*trayInSw=\d+$")


def _get_leonardo_port() -> str:
    return os.getenv("APP_LEONARDO_PORT", os.getenv("APP_ARDUINO_PORT", "/dev/ttyACM0"))


def _get_leonardo_baud() -> int:
    return int(os.getenv("APP_LEONARDO_BAUD", "115200"))


def _get_leonardo_read_timeout_s() -> float:
    return float(os.getenv("APP_LEONARDO_READ_TIMEOUT_S", "1.5"))


def _send_line(line: str):
    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            ser.write((line.strip() + "\n").encode("ascii", errors="ignore"))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to serial device on {port}: {exc}",
        ) from exc


def _send_with_response(command: str, timeout_s: Optional[float] = None) -> list[str]:
    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    read_timeout_s = timeout_s if timeout_s is not None else _get_leonardo_read_timeout_s()
    try:
        with serial.Serial(port, baudrate, timeout=0.2) as ser:
            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()
            ser.write((command.strip() + "\n").encode("ascii", errors="ignore"))
            started_at = time.time()
            lines: list[str] = []
            while time.time() - started_at < read_timeout_s:
                raw = ser.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="ignore").strip()
                if text:
                    lines.append(text)
            return lines
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to serial device on {port}: {exc}",
        ) from exc


def _extract_gate_position(lines: list[str]) -> Optional[str]:
    for line in reversed(lines):
        match = GATE_POSITION_PATTERN.match(line.strip())
        if match:
            return match.group(1)
    return None


def _extract_status_line(lines: list[str]) -> Optional[str]:
    for line in reversed(lines):
        if STATUS_LINE_PATTERN.match(line.strip()):
            return line.strip()
    return None


def _parse_status_values(status_line: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for part in status_line.split(","):
        chunk = part.strip()
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        values[key.strip()] = value.strip()
    return values


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


def _require_done(command: str, ack: bool, response: list[str]) -> dict:
    if not ack:
        raise HTTPException(status_code=504, detail=f"{command} did not acknowledge before timeout.")
    return {"command": command, "sent": True, "ack": True, "response": response}


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


def get_gate_position() -> dict:
    lines = _send_with_response("GATE_POS")
    position = _extract_gate_position(lines)
    return {
        "command": "GATE_POS",
        "position": position,
        "found": position is not None,
        "source": "gate_pos",
        "response": lines,
    }


def get_tray_position() -> dict:
    lines = _send_with_response("STATUS")
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


def home_machine() -> dict:
    return {"ok": True, "actions": [tray_in(), close_gate()]}


def emergency_stop() -> dict:
    _send_line("STOP_ALL")
    return {"command": "STOP_ALL", "sent": True}


def vacuum_on(raise_on_no_ack: bool = True) -> dict:
    lines = _send_with_response("VACUUM_ON")
    done = any("VACUUM_ON_DONE" in line for line in lines)
    if raise_on_no_ack:
        return _require_done("VACUUM_ON", done, lines)
    return {"command": "VACUUM_ON", "sent": True, "ack": done, "response": lines}


def vacuum_off(raise_on_no_ack: bool = True) -> dict:
    lines = _send_with_response("VACUUM_OFF")
    done = any("VACUUM_OFF_DONE" in line for line in lines)
    if raise_on_no_ack:
        return _require_done("VACUUM_OFF", done, lines)
    return {"command": "VACUUM_OFF", "sent": True, "ack": done, "response": lines}


def set_wrist1(angle: int) -> dict:
    angle = max(0, min(180, int(angle)))
    dwell_ms = int(os.getenv("APP_WRIST_DWELL_MS", "600"))
    lines = _send_with_response(f"SERVO1_POS:{angle}")
    time.sleep(dwell_ms / 1000.0)
    done = any(f"SERVO1_DONE:{angle}" in line for line in lines)
    return _require_done(f"SERVO1_POS:{angle}", done, lines) | {"angle": angle}


def set_wrist2(angle: int) -> dict:
    angle = max(0, min(180, int(angle)))
    dwell_ms = int(os.getenv("APP_WRIST_DWELL_MS", "600"))
    lines = _send_with_response(f"SERVO2_POS:{angle}")
    time.sleep(dwell_ms / 1000.0)
    done = any(f"SERVO2_DONE:{angle}" in line for line in lines)
    return _require_done(f"SERVO2_POS:{angle}", done, lines) | {"angle": angle}


def wrist_home() -> dict:
    return {"wrist1": set_wrist1(90), "wrist2": set_wrist2(90)}


def read_distance() -> dict:
    lines = _send_with_response("DIST_READ")
    for line in lines:
        if line.startswith("DIST="):
            try:
                return {"distance_cm": int(line.split("=", 1)[1].strip()), "found": True, "response": lines}
            except ValueError:
                pass
    return {"distance_cm": -1, "found": False, "response": lines}


def tray_to_gate_position() -> dict:
    _send_line("TRAY_OUT")
    return {"command": "TRAY_OUT", "sent": True}


def wait_for_gate_done(timeout_s: Optional[float] = None) -> dict:
    if timeout_s is None:
        timeout_s = float(os.getenv("APP_GATE_MOVE_TIMEOUT_S", "10"))
    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    try:
        with serial.Serial(port, baudrate, timeout=0.2) as ser:
            started = time.time()
            while time.time() - started < timeout_s:
                raw = ser.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="ignore").strip()
                if "GATE_OPEN_DONE" in text or "GATE_CLOSE_DONE" in text:
                    return {"done": True, "response": text}
            raise HTTPException(status_code=504, detail="Gate movement timed out.")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"wait_for_gate_done error: {exc}") from exc


def wait_for_tray_done(timeout_s: Optional[float] = None) -> dict:
    if timeout_s is None:
        timeout_s = float(os.getenv("APP_TRAY_MOVE_TIMEOUT_S", "10"))
    port = _get_leonardo_port()
    baudrate = _get_leonardo_baud()
    try:
        with serial.Serial(port, baudrate, timeout=0.2) as ser:
            started = time.time()
            while time.time() - started < timeout_s:
                raw = ser.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="ignore").strip()
                if "TRAY_OUT_DONE" in text or "TRAY_IN_DONE" in text:
                    return {"done": True, "response": text}
            raise HTTPException(status_code=504, detail="Tray movement timed out.")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"wait_for_tray_done error: {exc}") from exc
