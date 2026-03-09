from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import json
import os
import re
from pathlib import Path
from typing import Any


router = APIRouter()

IMEI_PATTERN = re.compile(r"^\d{15}$")
DEFAULT_LOOKUP_PATH = Path(__file__).resolve().parent.parent / "data" / "device_lookup_test.json"


class DeviceLookupRequest(BaseModel):
    imei: str = Field(min_length=1)


def _get_lookup_data_path() -> Path:
    configured = os.getenv("APP_IMEI_LOOKUP_DATA", "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_LOOKUP_PATH


def _normalize_imei(imei: str) -> str:
    digits_only = re.sub(r"\D", "", imei)
    if IMEI_PATTERN.match(digits_only) is None:
        raise HTTPException(status_code=400, detail="IMEI must contain exactly 15 digits.")
    return digits_only


def _read_lookup_data() -> dict[str, Any]:
    path = _get_lookup_data_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lookup data file not found: {path}",
        ) from e
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lookup data file is invalid JSON: {path}",
        ) from e

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Lookup data JSON must be an object.")
    return payload


def _extract_device_fields(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": str(entry.get("model", "Unknown device")),
        "max_value_eur": float(entry.get("max_value_eur", entry.get("max_value", 0))),
    }


def _resolve_device(imei: str, data: dict[str, Any]) -> dict[str, Any]:
    exact_map = data.get("exact", {})
    tac_map = data.get("tac", {})
    fallback = data.get("fallback", {"model": "Unknown device", "max_value_eur": 0})

    if isinstance(exact_map, dict) and imei in exact_map and isinstance(exact_map[imei], dict):
        return {"found": True, "source": "exact", **_extract_device_fields(exact_map[imei])}

    tac = imei[:8]
    if isinstance(tac_map, dict) and tac in tac_map and isinstance(tac_map[tac], dict):
        return {"found": True, "source": "tac", **_extract_device_fields(tac_map[tac])}

    if isinstance(fallback, dict):
        return {"found": False, "source": "fallback", **_extract_device_fields(fallback)}

    return {"found": False, "source": "fallback", "model": "Unknown device", "max_value_eur": 0.0}


@router.post("/device/lookup", tags=["Device"])
def lookup_device(payload: DeviceLookupRequest):
    normalized_imei = _normalize_imei(payload.imei)
    data = _read_lookup_data()
    resolved = _resolve_device(normalized_imei, data)

    return {
        "imei": normalized_imei,
        "found": resolved["found"],
        "source": resolved["source"],
        "model": resolved["model"],
        "max_value_eur": resolved["max_value_eur"],
    }
