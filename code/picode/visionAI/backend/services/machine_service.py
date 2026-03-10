import os
import re
import time
from typing import Optional

from fastapi import HTTPException
import serial  # type: ignore


GATE_POSITION_PATTERN = re.compile(r"^GATE_POS=(UP|DOWN|UNKNOWN)$")
STATUS_LINE_PATTERN = re.compile(r"^gateState=.*trayInSw=\d+$")


def _get_leonardo_port() -> str:
    # Keep backward compatibility with APP_ARDUINO_PORT.
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
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to serial device on {port}: {e}",
        ) from e


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
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to serial device on {port}: {e}",
        ) from e


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
    # Firmware uses INPUT_PULLUP and comments treat HIGH as "switch geraakt".
    tray_out_sw = values.get("trayOutSw")
    tray_in_sw = values.get("trayInSw")

    out_pressed = tray_out_sw == "1"
    in_pressed = tray_in_sw == "1"

    if out_pressed and not in_pressed:
        return "OUT"
    if in_pressed and not out_pressed:
        return "IN"
    return "UNKNOWN"


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
    # Firmware currently exposes tray switches via STATUS output.
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
    # Home = put tray in and close gate.
    tray = tray_in()
    gate = close_gate()
    return {"ok": True, "actions": [tray, gate]}


def emergency_stop() -> dict:
    _send_line("STOP_ALL")
    return {"command": "STOP_ALL", "sent": True}
