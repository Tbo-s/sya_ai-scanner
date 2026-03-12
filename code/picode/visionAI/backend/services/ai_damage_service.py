"""AI damage assessment service.

When APP_AI_DAMAGE_API_MOCK=1 (default) this module returns synthetic results
without calling any external service.  Set APP_AI_DAMAGE_API_MOCK=0 and
configure APP_AI_DAMAGE_API_URL to connect to a real grading API.
"""
from __future__ import annotations

import base64
import os
import random
from pathlib import Path
from typing import Optional

import requests
from fastapi import HTTPException
from pydantic import BaseModel


class AIDamageResult(BaseModel):
    imei: str
    session_id: str
    damage_score: float           # 0.0 = perfect, 1.0 = completely destroyed
    grade: str                    # "A" | "B" | "C" | "D" | "F"
    damage_details: list[str]     # e.g. ["minor_scratches", "screen_crack"]
    final_offer_eur: float
    photos_analyzed: int
    mock: bool


_DAMAGE_LABELS = [
    "minor_scratches",
    "screen_crack",
    "dent_corner",
    "missing_button",
    "back_glass_crack",
]

_GRADES = [
    (0.10, "A"),
    (0.25, "B"),
    (0.50, "C"),
    (0.75, "D"),
]


def _score_to_grade(score: float) -> str:
    for threshold, grade in _GRADES:
        if score < threshold:
            return grade
    return "F"


def _mock_result(
    imei: str,
    session_id: str,
    max_value_eur: float,
    photo_count: int,
) -> AIDamageResult:
    score = round(random.uniform(0.0, 0.4), 3)
    grade = _score_to_grade(score)
    num_issues = random.randint(0, 2)
    details = random.sample(_DAMAGE_LABELS, min(num_issues, len(_DAMAGE_LABELS)))
    offer = round(max_value_eur * (1.0 - score), 2)
    return AIDamageResult(
        imei=imei,
        session_id=session_id,
        damage_score=score,
        grade=grade,
        damage_details=details,
        final_offer_eur=offer,
        photos_analyzed=photo_count,
        mock=True,
    )


def _real_result(
    imei: str,
    session_id: str,
    max_value_eur: float,
    photo_paths: list[str],
) -> AIDamageResult:
    api_url = os.getenv("APP_AI_DAMAGE_API_URL", "http://localhost:4000/api/v1/analyze")

    photos_payload = []
    for path_str in photo_paths:
        path = Path(path_str)
        if not path.exists():
            continue
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        photos_payload.append({"label": path.stem, "data": data})

    try:
        resp = requests.post(
            api_url,
            json={"imei": imei, "session_id": session_id, "photos": photos_payload},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI damage API error: {e}",
        ) from e

    score = float(body.get("damage_score", 0.0))
    return AIDamageResult(
        imei=imei,
        session_id=session_id,
        damage_score=score,
        grade=body.get("grade", _score_to_grade(score)),
        damage_details=body.get("damage_details", []),
        final_offer_eur=float(body.get("final_offer_eur", round(max_value_eur * (1 - score), 2))),
        photos_analyzed=len(photos_payload),
        mock=False,
    )


def analyze_photos(
    imei: str,
    session_id: str,
    photo_paths: list[str],
    max_value_eur: float,
) -> AIDamageResult:
    use_mock = os.getenv("APP_AI_DAMAGE_API_MOCK", "1").strip().lower() in {"1", "true", "yes", "on"}
    if use_mock:
        return _mock_result(imei, session_id, max_value_eur, len(photo_paths))
    return _real_result(imei, session_id, max_value_eur, photo_paths)