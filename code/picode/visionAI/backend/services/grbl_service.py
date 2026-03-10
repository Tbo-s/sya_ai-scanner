import os
import re
import time
from typing import Any

from fastapi import HTTPException
import serial  # type: ignore


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
    # Example: "$X|$H"
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

            return {"command": normalized, "ack": "timeout", "response": lines}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to talk to GRBL on {port}: {e}",
        ) from e


def _parse_sequence(raw_sequence: str) -> list[str]:
    parts = re.split(r"[|\n;]+", raw_sequence)
    return [part.strip() for part in parts if part.strip()]


def run_postflow_sequence(force: bool = False) -> dict[str, Any]:
    if not force and not _get_postflow_enabled():
        return {
            "executed": False,
            "reason": "disabled",
            "sequence": _parse_sequence(_get_postflow_sequence()),
            "results": [],
        }

    sequence = _parse_sequence(_get_postflow_sequence())
    results = []
    for command in sequence:
        wait_for_ok = command != "!"
        results.append(send_grbl(command, wait_for_ok=wait_for_ok))

    return {
        "executed": True,
        "sequence": sequence,
        "results": results,
    }
