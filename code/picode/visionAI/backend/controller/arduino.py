from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

import serial  # type: ignore


router = APIRouter()


class ServoState(BaseModel):
    enabled: bool


def _get_serial_port() -> str:
    # Default for Arduino Leonardo on Linux/Raspberry Pi
    return os.getenv("APP_ARDUINO_PORT", "/dev/ttyACM0")


def _write_servo_state(enabled: bool):
    port = _get_serial_port()
    try:
        with serial.Serial(port, 9600, timeout=1) as ser:
            ser.write(b"1\n" if enabled else b"0\n")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to Arduino on {port}: {e}",
        ) from e


@router.post("/arduino/servo", tags=["Arduino"])
def set_servo(state: ServoState):
    _write_servo_state(state.enabled)
    return {"enabled": state.enabled}

