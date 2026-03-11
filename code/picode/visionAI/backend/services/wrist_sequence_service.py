import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from fastapi import HTTPException

from services.machine_service import send_leonardo_command


LOGICAL_MIN = -90
LOGICAL_CENTER = 0
LOGICAL_MAX = 90


@dataclass
class ServoLogicalConfig:
    min_angle: int
    center_angle: int
    max_angle: int
    inverted: bool


WRIST_SEQUENCE_STEPS = [
    {"name": "S1_START_MINUS_90", "servo": "servo1", "logical_angle": -90},
    {"name": "S1_TO_CENTER_0", "servo": "servo1", "logical_angle": 0},
    {"name": "S2_START_CENTER_0", "servo": "servo2", "logical_angle": 0},
    {"name": "S2_TO_MINUS_90", "servo": "servo2", "logical_angle": -90},
    {"name": "S2_TO_PLUS_90", "servo": "servo2", "logical_angle": 90},
    {"name": "S1_TO_PLUS_90", "servo": "servo1", "logical_angle": 90},
    {"name": "S1_BACK_TO_MINUS_90", "servo": "servo1", "logical_angle": -90},
    {"name": "S2_BACK_TO_CENTER_0", "servo": "servo2", "logical_angle": 0},
]


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "1" if default else "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _read_servo_config(prefix: str) -> ServoLogicalConfig:
    min_angle = int(os.getenv(f"{prefix}_MIN_ANGLE", "0"))
    center_angle = int(os.getenv(f"{prefix}_CENTER_ANGLE", "90"))
    max_angle = int(os.getenv(f"{prefix}_MAX_ANGLE", "180"))
    inverted = _env_flag(f"{prefix}_INVERTED", default=False)
    return ServoLogicalConfig(
        min_angle=min_angle,
        center_angle=center_angle,
        max_angle=max_angle,
        inverted=inverted,
    )


def _default_servo_configs() -> dict[str, ServoLogicalConfig]:
    return {
        "servo1": _read_servo_config("APP_WRIST_SERVO1"),
        "servo2": _read_servo_config("APP_WRIST_SERVO2"),
    }


def _default_step_delay_ms() -> int:
    return int(os.getenv("APP_WRIST_SEQUENCE_STEP_DELAY_MS", "500"))


def _build_servo_command(servo_key: str, physical_angle: int, logical_angle: int) -> str:
    env_name = "APP_WRIST_SERVO1_CMD_TEMPLATE" if servo_key == "servo1" else "APP_WRIST_SERVO2_CMD_TEMPLATE"
    default_template = "WRIST1:{angle}" if servo_key == "servo1" else "WRIST2:{angle}"
    template = os.getenv(env_name, default_template)
    try:
        rendered = template.format(
            angle=physical_angle,
            logical_angle=logical_angle,
            servo=1 if servo_key == "servo1" else 2,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid wrist command template {env_name}: {e}") from e
    return rendered.strip()


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _validate_servo_config(config: ServoLogicalConfig):
    for field_name in ("min_angle", "center_angle", "max_angle"):
        value = getattr(config, field_name)
        if value < 0 or value > 180:
            raise HTTPException(status_code=400, detail=f"{field_name} must be in range [0, 180].")

    if not (config.min_angle <= config.center_angle <= config.max_angle):
        raise HTTPException(
            status_code=400,
            detail="Servo config invalid: require min_angle <= center_angle <= max_angle.",
        )


def map_logical_to_physical_angle(logical_angle: int, config: ServoLogicalConfig) -> int:
    _validate_servo_config(config)

    if logical_angle < LOGICAL_MIN or logical_angle > LOGICAL_MAX:
        raise HTTPException(status_code=400, detail="Logical angle must be in range [-90, 90].")

    effective_logical = -logical_angle if config.inverted else logical_angle

    if effective_logical <= LOGICAL_CENTER:
        # Piecewise linear mapping from [-90..0] -> [min..center].
        t = (effective_logical - LOGICAL_MIN) / float(LOGICAL_CENTER - LOGICAL_MIN)
        physical = config.min_angle + t * (config.center_angle - config.min_angle)
    else:
        # Piecewise linear mapping from [0..90] -> [center..max].
        t = (effective_logical - LOGICAL_CENTER) / float(LOGICAL_MAX - LOGICAL_CENTER)
        physical = config.center_angle + t * (config.max_angle - config.center_angle)

    rounded = int(round(physical))
    clamped = _clamp(rounded, config.min_angle, config.max_angle)
    return clamped


def _normalize_config_payload(
    config_payload: Optional[Dict[str, Any]], default_config: ServoLogicalConfig
) -> ServoLogicalConfig:
    if not config_payload:
        _validate_servo_config(default_config)
        return default_config

    merged = ServoLogicalConfig(
        min_angle=int(config_payload.get("min_angle", default_config.min_angle)),
        center_angle=int(config_payload.get("center_angle", default_config.center_angle)),
        max_angle=int(config_payload.get("max_angle", default_config.max_angle)),
        inverted=bool(config_payload.get("inverted", default_config.inverted)),
    )
    _validate_servo_config(merged)
    return merged


def run_wrist_sequence(
    simulate: bool = False,
    step_delay_ms: Optional[int] = None,
    servo1_config_payload: Optional[Dict[str, Any]] = None,
    servo2_config_payload: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    delay_ms = _default_step_delay_ms() if step_delay_ms is None else int(step_delay_ms)
    if delay_ms < 0 or delay_ms > 10000:
        raise HTTPException(status_code=400, detail="step_delay_ms must be in range [0, 10000].")

    defaults = _default_servo_configs()
    servo_configs = {
        "servo1": _normalize_config_payload(servo1_config_payload, defaults["servo1"]),
        "servo2": _normalize_config_payload(servo2_config_payload, defaults["servo2"]),
    }

    results = []
    for idx, step in enumerate(WRIST_SEQUENCE_STEPS):
        servo_key = step["servo"]
        logical_angle = int(step["logical_angle"])
        config = servo_configs[servo_key]
        physical_angle = map_logical_to_physical_angle(logical_angle=logical_angle, config=config)
        command = _build_servo_command(
            servo_key=servo_key,
            physical_angle=physical_angle,
            logical_angle=logical_angle,
        )

        if not simulate:
            send_leonardo_command(command)

        results.append(
            {
                "index": idx + 1,
                "name": step["name"],
                "servo": servo_key,
                "logical_angle": logical_angle,
                "physical_angle": physical_angle,
                "command": command,
                "sent": not simulate,
            }
        )

        if idx < len(WRIST_SEQUENCE_STEPS) - 1 and delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    return {
        "simulate": simulate,
        "step_delay_ms": delay_ms,
        "servo_config": {
            "servo1": asdict(servo_configs["servo1"]),
            "servo2": asdict(servo_configs["servo2"]),
        },
        "sequence": results,
    }
