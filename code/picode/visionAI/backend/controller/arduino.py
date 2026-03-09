from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import os
import re
import time
from typing import Any, Optional

import serial  # type: ignore
from serial.tools import list_ports  # type: ignore


router = APIRouter()


class ServoState(BaseModel):
    enabled: bool


class GrblCommand(BaseModel):
    command: str = Field(min_length=1)
    wait_for_ok: bool = True


class GateCommand(BaseModel):
    command: str = Field(min_length=1)


GRBL_ALLOWED_CHARS = re.compile(r"^[A-Za-z0-9\s\$\?\~\!\+\-\.\,\=\#\:\;\/\*\(\)]+$")
ARDUINO_USB_VIDS = {0x2341, 0x2A03}
ARDUINO_LEONARDO_PIDS = {0x0036, 0x8036}
ARDUINO_MEGA_PIDS = {0x0010, 0x0042, 0x0242}
ALLOWED_GATE_COMMANDS = {"GATE_OPEN", "GATE_CLOSE"}


def _get_leonardo_port() -> str:
    # Keep backward compatibility with APP_ARDUINO_PORT.
    return os.getenv("APP_LEONARDO_PORT", os.getenv("APP_ARDUINO_PORT", "/dev/ttyACM0"))


def _get_leonardo_baud() -> int:
    return int(os.getenv("APP_LEONARDO_BAUD", "9600"))


def _get_grbl_port() -> str:
    return os.getenv("APP_GRBL_PORT", "/dev/ttyACM1")


def _get_grbl_baud() -> int:
    return int(os.getenv("APP_GRBL_BAUD", "115200"))


def _get_grbl_read_timeout_s() -> float:
    return float(os.getenv("APP_GRBL_READ_TIMEOUT_S", "1.5"))


def _send_line(port: str, baudrate: int, line: str):
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            ser.write((line.strip() + "\n").encode("ascii", errors="ignore"))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to serial device on {port}: {e}",
        ) from e


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _infer_board_role(vid: Optional[int], pid: Optional[int], text_blob: str) -> str:
    txt = text_blob.lower()

    if vid in ARDUINO_USB_VIDS and pid in ARDUINO_LEONARDO_PIDS:
        return "leonardo"
    if vid in ARDUINO_USB_VIDS and pid in ARDUINO_MEGA_PIDS:
        return "mega"

    if "leonardo" in txt:
        return "leonardo"
    if "mega" in txt or "grbl" in txt or "ch340" in txt:
        return "mega"

    return "unknown"


def _serialize_port(port_info: Any) -> dict[str, Any]:
    device = _safe_text(getattr(port_info, "device", ""))
    description = _safe_text(getattr(port_info, "description", ""))
    manufacturer = _safe_text(getattr(port_info, "manufacturer", ""))
    product = _safe_text(getattr(port_info, "product", ""))
    hwid = _safe_text(getattr(port_info, "hwid", ""))
    serial_number = _safe_text(getattr(port_info, "serial_number", ""))
    interface = _safe_text(getattr(port_info, "interface", ""))
    location = _safe_text(getattr(port_info, "location", ""))
    vid = getattr(port_info, "vid", None)
    pid = getattr(port_info, "pid", None)

    text_blob = " ".join([description, manufacturer, product, hwid, interface])
    board_role = _infer_board_role(vid=vid, pid=pid, text_blob=text_blob)

    return {
        "device": device,
        "description": description,
        "manufacturer": manufacturer,
        "product": product,
        "serial_number": serial_number,
        "interface": interface,
        "location": location,
        "hwid": hwid,
        "vid": f"{vid:04X}" if isinstance(vid, int) else None,
        "pid": f"{pid:04X}" if isinstance(pid, int) else None,
        "board_role": board_role,
    }


def _compute_port_suggestions(ports: list[dict[str, Any]]) -> dict[str, Any]:
    leonardo_candidates = [p["device"] for p in ports if p.get("board_role") == "leonardo"]
    mega_candidates = [p["device"] for p in ports if p.get("board_role") == "mega"]

    return {
        "leonardo_port": leonardo_candidates[0] if leonardo_candidates else None,
        "grbl_port": mega_candidates[0] if mega_candidates else None,
        "confidence": "high" if leonardo_candidates or mega_candidates else "low",
        "notes": "Set APP_LEONARDO_PORT and APP_GRBL_PORT with the suggested values if correct.",
    }


def _write_servo_state(enabled: bool):
    _send_line(
        port=_get_leonardo_port(),
        baudrate=_get_leonardo_baud(),
        line="1" if enabled else "0",
    )


def _normalize_gate_command(command: str) -> str:
    normalized = command.strip().upper()
    if normalized not in ALLOWED_GATE_COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid gate command. Allowed: {sorted(ALLOWED_GATE_COMMANDS)}",
        )
    return normalized


def _write_gate_command(command: str):
    normalized = _normalize_gate_command(command)
    _send_line(
        port=_get_leonardo_port(),
        baudrate=_get_leonardo_baud(),
        line=normalized,
    )


def _is_safe_grbl_command(command: str) -> bool:
    command = command.strip()
    if not command:
        return False
    return GRBL_ALLOWED_CHARS.match(command) is not None


def _send_grbl(command: str, wait_for_ok: bool = True):
    normalized = command.strip()
    if not _is_safe_grbl_command(normalized):
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

            return {"command": normalized, "ack": "timeout", "response": lines}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to GRBL on {port}: {e}",
        ) from e


@router.post("/arduino/servo", tags=["Arduino"])
def set_servo(state: ServoState):
    # Backward-compatible endpoint used by the frontend.
    _write_servo_state(state.enabled)
    return {"enabled": state.enabled}


@router.post("/arduino/leonardo/servo", tags=["Arduino"])
def set_leonardo_servo(state: ServoState):
    _write_servo_state(state.enabled)
    return {"enabled": state.enabled}


@router.post("/arduino/leonardo/gate", tags=["Arduino"])
def send_leonardo_gate_command(payload: GateCommand):
    normalized = _normalize_gate_command(payload.command)
    _write_gate_command(normalized)
    return {"command": normalized}


@router.post("/arduino/grbl/command", tags=["Arduino"])
def grbl_command(payload: GrblCommand):
    return _send_grbl(payload.command, wait_for_ok=payload.wait_for_ok)


@router.post("/arduino/grbl/unlock", tags=["Arduino"])
def grbl_unlock():
    return _send_grbl("$X")


@router.post("/arduino/grbl/home", tags=["Arduino"])
def grbl_home():
    return _send_grbl("$H")


@router.post("/arduino/grbl/stop", tags=["Arduino"])
def grbl_stop():
    # Feed hold / immediate stop signal for GRBL.
    return _send_grbl("!", wait_for_ok=False)


@router.get("/arduino/ports", tags=["Arduino"])
def list_arduino_ports():
    try:
        ports = [_serialize_port(p) for p in list_ports.comports()]
        suggestions = _compute_port_suggestions(ports)
        return {
            "ports": ports,
            "suggested": suggestions,
            "configured": {
                "APP_LEONARDO_PORT": _get_leonardo_port(),
                "APP_GRBL_PORT": _get_grbl_port(),
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enumerate serial ports: {e}",
        ) from e
