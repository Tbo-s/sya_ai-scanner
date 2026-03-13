from __future__ import annotations

import os
from typing import Any


def _is_enabled(env_name: str, default: str = "0") -> bool:
    return os.getenv(env_name, default).strip().lower() in {"1", "true", "yes", "on"}


def get_runtime_settings() -> dict[str, Any]:
    return {
        "auto_safe_idle_on_boot": _is_enabled("APP_MACHINE_SAFE_IDLE_ON_BOOT", "1"),
        "auto_grbl_boot_sequence": _is_enabled("APP_GRBL_BOOT_SEQUENCE_ENABLED", "0"),
        "grbl_boot_sequence": os.getenv("APP_GRBL_BOOT_SEQUENCE", "$X|$H"),
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
    sequence = os.getenv("APP_GRBL_BOOT_SEQUENCE", "$X|$H")
    results.append({"step": "grbl_home", "result": grbl_service.run_sequence(sequence, enabled=True)})
    return {"ok": True, "results": results}


def boot_initialize() -> dict[str, Any]:
    from services import grbl_service

    report = {
        "safe_idle": None,
        "grbl_boot": None,
        "errors": [],
    }

    if _is_enabled("APP_MACHINE_SAFE_IDLE_ON_BOOT", "1"):
        try:
            report["safe_idle"] = safe_idle_state()
        except Exception as exc:
            report["errors"].append({"step": "safe_idle", "error": str(exc)})

    if _is_enabled("APP_GRBL_BOOT_SEQUENCE_ENABLED", "0"):
        try:
            report["grbl_boot"] = grbl_service.run_sequence(os.getenv("APP_GRBL_BOOT_SEQUENCE", "$X|$H"), enabled=True)
        except Exception as exc:
            report["errors"].append({"step": "grbl_boot", "error": str(exc)})

    report["ok"] = not report["errors"]
    return report
