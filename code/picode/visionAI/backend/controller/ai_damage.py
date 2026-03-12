from fastapi import APIRouter
from pydantic import BaseModel
from services.ai_damage_service import AIDamageResult, analyze_photos

router = APIRouter()


class AnalyzeRequest(BaseModel):
    imei: str
    session_id: str
    photo_paths: list[str]
    max_value_eur: float


@router.post("/ai/analyze", response_model=AIDamageResult, tags=["AI"])
def analyze(payload: AnalyzeRequest) -> AIDamageResult:
    return analyze_photos(
        imei=payload.imei,
        session_id=payload.session_id,
        photo_paths=payload.photo_paths,
        max_value_eur=payload.max_value_eur,
    )