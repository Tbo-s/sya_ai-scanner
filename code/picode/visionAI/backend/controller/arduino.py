from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import os
import re
import time
from typing import Any, Optional

import serial  # type: ignore
from serial.tools import list_ports  # type: ignore
from services.grbl_service import (
    is_safe_grbl_command as service_is_safe_grbl_command,
    run_postflow_sequence,
    send_grbl,
)
from services.machine_service import (
    close_gate as machine_close_gate,
    emergency_stop as machine_emergency_stop,
    get_gate_position as machine_get_gate_position,
    get_tray_position as machine_get_tray_position,
    home_machine as machine_home_machine,
    open_gate as machine_open_gate,
    tray_in as machine_tray_in,
    tray_out as machine_tray_out,
)
from services.wrist_sequence_service import run_wrist_sequence


router = APIRouter()


class ServoState(BaseModel):
    enabled: bool


class GrblCommand(BaseModel):
    command: str = Field(min_length=1)
    wait_for_ok: bool = True


class GateCommand(BaseModel):
    command: str = Field(min_length=1)

class TrayCommand(BaseModel):
    command: str = Field(min_length=1)


class WristServoConfigPayload(BaseModel):
    min_angle: int = Field(ge=0, le=180)
    center_angle: int = Field(ge=0, le=180)
    max_angle: int = Field(ge=0, le=180)
    inverted: bool = False


class WristSequenceRequest(BaseModel):
    simulate: bool = False
    step_delay_ms: Optional[int] = Field(default=None, ge=0, le=10000)
    servo1: Optional[WristServoConfigPayload] = None
    servo2: Optional[WristServoConfigPayload] = None


GATE_POSITION_PATTERN = re.compile(r"^GATE_POS=(UP|DOWN|UNKNOWN)$")
ARDUINO_USB_VIDS = {0x2341, 0x2A03}
ARDUINO_LEONARDO_PIDS = {0x0036, 0x8036}
ARDUINO_MEGA_PIDS = {0x0010, 0x0042, 0x0242}
ALLOWED_GATE_COMMANDS = {"GATE_OPEN", "GATE_CLOSE"}
ALLOWED_TRAY_COMMANDS = {"TRAY_OUT", "TRAY_IN"}


def _get_leonardo_port() -> str:
    # Keep backward compatibility with APP_ARDUINO_PORT.
    return os.getenv("APP_LEONARDO_PORT", os.getenv("APP_ARDUINO_PORT", "/dev/ttyACM0"))


def _get_leonardo_baud() -> int:
    return int(os.getenv("APP_LEONARDO_BAUD", "115200"))


def _get_grbl_port() -> str:
    return os.getenv("APP_GRBL_PORT", "/dev/ttyACM1")


def _get_grbl_baud() -> int:
    return int(os.getenv("APP_GRBL_BAUD", "115200"))


def _get_grbl_read_timeout_s() -> float:
    return float(os.getenv("APP_GRBL_READ_TIMEOUT_S", "1.5"))


def _get_leonardo_read_timeout_s() -> float:
    return float(os.getenv("APP_LEONARDO_READ_TIMEOUT_S", "1.5"))


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


def _send_leonardo_with_response(command: str, timeout_s: Optional[float] = None) -> list[str]:
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
                if not text:
                    continue
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


def _is_safe_grbl_command(command: str) -> bool:
    return service_is_safe_grbl_command(command)


def _send_grbl(command: str, wait_for_ok: bool = True):
    return send_grbl(command, wait_for_ok=wait_for_ok)


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
    if normalized == "GATE_OPEN":
        machine_open_gate()
    else:
        machine_close_gate()
    return {"command": normalized}


@router.get("/arduino/leonardo/gate-position", tags=["Arduino"])
def get_leonardo_gate_position():
    return machine_get_gate_position()


@router.post("/arduino/leonardo/tray", tags=["Arduino"])
def send_leonardo_tray_command(payload: TrayCommand):
    normalized = payload.command.strip().upper()
    if normalized not in ALLOWED_TRAY_COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tray command. Allowed: {sorted(ALLOWED_TRAY_COMMANDS)}",
        )

    if normalized == "TRAY_OUT":
        machine_tray_out()
    else:
        machine_tray_in()
    return {"command": normalized}


@router.get("/arduino/leonardo/tray-position", tags=["Arduino"])
def get_leonardo_tray_position():
    return machine_get_tray_position()


@router.post("/arduino/leonardo/home", tags=["Arduino"])
def home_leonardo_machine():
    return machine_home_machine()


@router.post("/arduino/leonardo/emergency-stop", tags=["Arduino"])
def emergency_stop_leonardo_machine():
    return machine_emergency_stop()


@router.post("/arduino/leonardo/wrist-sequence", tags=["Arduino"])
def run_leonardo_wrist_sequence(payload: WristSequenceRequest):
    return run_wrist_sequence(
        simulate=payload.simulate,
        step_delay_ms=payload.step_delay_ms,
        servo1_config_payload=payload.servo1.dict() if payload.servo1 else None,
        servo2_config_payload=payload.servo2.dict() if payload.servo2 else None,
    )


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


@router.post("/arduino/grbl/post-flow", tags=["Arduino"])
def grbl_post_flow():
    # Configurable sequence for automated NEMA actions at end-of-flow.
    return run_postflow_sequence(force=False)


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
