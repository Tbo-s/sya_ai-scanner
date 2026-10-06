from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


WRIST_PRESET_DEFAULTS: dict[str, list[dict[str, Any]]] = {
    "wrist1": [
        {"key": "camera", "label": "Camerakant", "logical": 53},
        {"key": "wall", "label": "Muurkant", "logical": 95},
        {"key": "gate", "label": "Gatekant", "logical": 132},
    ],
    "wrist2": [
        {"key": "horizontal", "label": "Horizontaal", "logical": -9},
        {"key": "vertical_left", "label": "Verticaal links", "logical": 58},
        {"key": "vertical_right", "label": "Verticaal rechts", "logical": -90},
    ],
}


def _preset_file() -> Path:
    configured = os.getenv("APP_WRIST_PRESETS_FILE", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "config" / "wrist_presets.json"


def _wrist_key(wrist_index: int) -> str:
    if wrist_index not in (1, 2):
        raise ValueError("wrist_index must be 1 or 2")
    return f"wrist{wrist_index}"


def _angle_bounds(wrist_index: int) -> tuple[int, int]:
    wrist_key = _wrist_key(wrist_index).upper()
    default_min = "32" if wrist_index == 1 else "-90"
    default_max = "152" if wrist_index == 1 else "90"
    min_angle = int(os.getenv(f"APP_{wrist_key}_MIN_ANGLE", default_min))
    max_angle = int(os.getenv(f"APP_{wrist_key}_MAX_ANGLE", default_max))
    return (min(min_angle, max_angle), max(min_angle, max_angle))


def _clamp_angle(wrist_index: int, angle: int) -> int:
    min_angle, max_angle = _angle_bounds(wrist_index)
    return max(min_angle, min(max_angle, int(angle)))


def _read_saved_presets() -> dict[str, dict[str, int]]:
    path = _preset_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}

    saved: dict[str, dict[str, int]] = {}
    if not isinstance(data, dict):
        return saved

    for wrist_key in ("wrist1", "wrist2"):
        wrist_values = data.get(wrist_key)
        if not isinstance(wrist_values, dict):
            continue
        saved[wrist_key] = {}
        wrist_index = int(wrist_key[-1])
        for preset_key, angle in wrist_values.items():
            try:
                saved[wrist_key][str(preset_key)] = _clamp_angle(wrist_index, int(angle))
            except (TypeError, ValueError):
                continue

    return saved


def _write_saved_presets(saved: dict[str, dict[str, int]]) -> None:
    path = _preset_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(saved, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(path)


def get_wrist_presets() -> dict[str, list[dict[str, Any]]]:
    saved = _read_saved_presets()
    result: dict[str, list[dict[str, Any]]] = {}

    for wrist_key, defaults in WRIST_PRESET_DEFAULTS.items():
        wrist_index = int(wrist_key[-1])
        saved_wrist = saved.get(wrist_key, {})
        result[wrist_key] = [
            {
                **preset,
                "logical": _clamp_angle(wrist_index, saved_wrist.get(preset["key"], preset["logical"])),
            }
            for preset in defaults
        ]

    return result


def update_wrist_preset(wrist_index: int, preset_key: str, logical_angle: int) -> dict[str, Any]:
    wrist_key = _wrist_key(wrist_index)
    known_presets = {preset["key"]: preset for preset in WRIST_PRESET_DEFAULTS[wrist_key]}
    if preset_key not in known_presets:
        raise ValueError(f"Unknown {wrist_key} preset: {preset_key}")

    saved = _read_saved_presets()
    saved.setdefault(wrist_key, {})
    saved[wrist_key][preset_key] = _clamp_angle(wrist_index, logical_angle)
    _write_saved_presets(saved)

    updated = next(preset for preset in get_wrist_presets()[wrist_key] if preset["key"] == preset_key)
    return {"wrist": wrist_key, "preset": updated, "presets": get_wrist_presets()}
