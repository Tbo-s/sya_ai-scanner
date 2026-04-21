from __future__ import annotations

import os
from typing import Any


def _is_enabled(env_name: str, default: str = "0") -> bool:
    return os.getenv(env_name, default).strip().lower() in {"1", "true", "yes", "on"}


def _limit_toward_zero_sign(axis: str) -> int:
    raw = os.getenv(f"APP_GRBL_{axis.upper()}_LIMIT_TOWARD_ZERO_SIGN", "-1").strip().lower()
    return 1 if raw in {"1", "+1", "+", "positive", "pos"} else -1


def get_runtime_settings() -> dict[str, Any]:
    return {
        "auto_safe_idle_on_boot": _is_enabled("APP_MACHINE_SAFE_IDLE_ON_BOOT", "1"),
        "auto_grbl_home_on_boot": _is_enabled("APP_GRBL_HOME_ON_BOOT", "1"),
        "auto_grbl_boot_sequence": _is_enabled("APP_GRBL_BOOT_SEQUENCE_ENABLED", "0"),
        "auto_grbl_test_spin_on_ui_start": _is_enabled("APP_GRBL_TEST_SPIN_ON_UI_START", "1"),
        "grbl_boot_sequence": os.getenv("APP_GRBL_BOOT_SEQUENCE", "$X|$H"),
        "grbl_manual_xy_step": float(os.getenv("APP_GRBL_MANUAL_XY_STEP", "1.0")),
        "grbl_manual_xy_feed_rate": int(os.getenv("APP_GRBL_MANUAL_XY_FEED_RATE", "120")),
        "grbl_home_xy_feed_rate": int(os.getenv("APP_GRBL_HOME_XY_FEED_RATE", "120")),
        "grbl_limit_pin_mode": os.getenv("APP_GRBL_LIMIT_PIN_MODE", "active_present").strip(),
        "grbl_limit_toward_zero_sign": {
            "x": _limit_toward_zero_sign("X"),
            "y": _limit_toward_zero_sign("Y"),
        },
        "frontend_dist_dir": os.getenv("APP_FRONTEND_DIST", "").strip() or "frontend/dist",
        "camera_index": int(os.getenv("APP_CAMERA_INDEX", "0")),
        "photo_storage_dir": os.getenv("APP_PHOTO_STORAGE_DIR", "/tmp/sya_photos"),
    }


def safe_idle_state() -> dict[str, Any]:
    from controller.camera import camera_manager
    from services import machine_service

    results = []
    errors = []

    for label, func in (
        ("camera_stop", camera_manager.stop),
        ("vacuum_off", lambda: machine_service.vacuum_off(raise_on_no_ack=False)),
        ("wrist_home", machine_service.wrist_home),
        ("tray_in_gate_close", machine_service.home_machine),
    ):
        try:
            results.append({"step": label, "result": func()})
        except Exception as exc:
            errors.append({"step": label, "error": str(exc)})

    return {"ok": not errors, "results": results, "errors": errors}


def home_axes() -> dict[str, Any]:
    from services import grbl_service, machine_service

    results = []
    results.append({"step": "leonardo_home", "result": machine_service.home_machine()})
    results.append({"step": "grbl_home_xy", "result": grbl_service.home_xy_to_limits()})
    return {"ok": True, "results": results}


def boot_initialize() -> dict[str, Any]:
    from services import grbl_service

    report = {
        "safe_idle": None,
        "grbl_home_xy": None,
        "grbl_boot": None,
        "errors": [],
    }

    if _is_enabled("APP_MACHINE_SAFE_IDLE_ON_BOOT", "1"):
        try:
            report["safe_idle"] = safe_idle_state()
        except Exception as exc:
            report["errors"].append({"step": "safe_idle", "error": str(exc)})

    if _is_enabled("APP_GRBL_HOME_ON_BOOT", "1"):
        try:
            report["grbl_home_xy"] = grbl_service.home_xy_to_limits()
        except Exception as exc:
            report["errors"].append({"step": "grbl_home_xy", "error": str(exc)})

    if _is_enabled("APP_GRBL_BOOT_SEQUENCE_ENABLED", "0"):
        try:
            report["grbl_boot"] = grbl_service.run_sequence(os.getenv("APP_GRBL_BOOT_SEQUENCE", "$X|$H"), enabled=True)
        except Exception as exc:
            report["errors"].append({"step": "grbl_boot", "error": str(exc)})

    report["ok"] = not report["errors"]
    return report
