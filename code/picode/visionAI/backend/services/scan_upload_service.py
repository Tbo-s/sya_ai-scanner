"""Optional upload of completed scan data and photos."""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Optional

import requests
from fastapi import HTTPException


def _is_enabled(env_name: str, default: str = "0") -> bool:
    return os.getenv(env_name, default).strip().lower() in {"1", "true", "yes", "on"}


def _get_upload_url() -> str:
    return os.getenv("APP_SCAN_RESULTS_UPLOAD_URL", "").strip()


def _get_timeout_s() -> float:
    return max(1.0, float(os.getenv("APP_SCAN_RESULTS_UPLOAD_TIMEOUT_S", "30")))


def _build_photo_payload(photo_paths: list[str]) -> list[dict[str, Any]]:
    photos = []
    for path_str in photo_paths:
        path = Path(path_str)
        if not path.exists() or not path.is_file():
            continue
        photos.append(
            {
                "label": path.stem,
                "filename": path.name,
                "content_type": "image/jpeg",
                "data_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )
    return photos


def build_scan_upload_payload(
    *,
    imei: str,
    session_id: str,
    device_model: str,
    max_value_eur: float,
    photo_paths: list[str],
    ai_result: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    photos = _build_photo_payload(photo_paths)
    return {
        "imei": imei,
        "session_id": session_id,
        "device_model": device_model,
        "max_value_eur": max_value_eur,
        "photo_count": len(photos),
        "photos": photos,
        "ai_result": ai_result,
    }


def upload_scan_results(
    *,
    imei: str,
    session_id: str,
    device_model: str,
    max_value_eur: float,
    photo_paths: list[str],
    ai_result: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    enabled = _is_enabled("APP_SCAN_RESULTS_UPLOAD_ENABLED", "0")
    required = _is_enabled("APP_SCAN_RESULTS_UPLOAD_REQUIRED", "0")
    url = _get_upload_url()

    if not enabled:
        return {"enabled": False, "skipped": True, "reason": "disabled"}
    if not url:
        result = {"enabled": True, "skipped": True, "reason": "missing_url"}
        if required:
            raise HTTPException(status_code=500, detail=result)
        return result

    payload = build_scan_upload_payload(
        imei=imei,
        session_id=session_id,
        device_model=device_model,
        max_value_eur=max_value_eur,
        photo_paths=photo_paths,
        ai_result=ai_result,
    )

    try:
        response = requests.post(url, json=payload, timeout=_get_timeout_s())
        response.raise_for_status()
    except Exception as exc:
        result = {"enabled": True, "skipped": False, "ok": False, "url": url, "error": str(exc)}
        if required:
            raise HTTPException(status_code=502, detail=result) from exc
        return result

    response_payload: Any
    try:
        response_payload = response.json()
    except ValueError:
        response_payload = response.text[:1000]

    return {
        "enabled": True,
        "skipped": False,
        "ok": True,
        "url": url,
        "status_code": response.status_code,
        "photo_count": payload["photo_count"],
        "response": response_payload,
    }
