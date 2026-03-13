from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.scan_orchestrator import ScanOrchestrator

router = APIRouter()

_orchestrator: Optional[ScanOrchestrator] = None


def set_orchestrator(orchestrator: ScanOrchestrator):
    global _orchestrator
    _orchestrator = orchestrator


def get_orchestrator() -> ScanOrchestrator:
    if _orchestrator is None:
        raise HTTPException(status_code=500, detail="Orchestrator not initialised.")
    return _orchestrator


class StartScanRequest(BaseModel):
    imei: str
    device_model: str
    max_value_eur: float


@router.post("/scan/start", tags=["Scan"])
async def start_scan(payload: StartScanRequest):
    session = await get_orchestrator().start_scan(
        imei=payload.imei,
        device_model=payload.device_model,
        max_value_eur=payload.max_value_eur,
    )
    return {"session_id": session.session_id, "status": session.status}


@router.post("/scan/confirm", tags=["Scan"])
async def confirm_user():
    await get_orchestrator().confirm_user_action()
    return {"ok": True}


@router.get("/scan/status", tags=["Scan"])
def scan_status():
    status = get_orchestrator().get_status()
    if status is None:
        return {"status": "idle"}
    return status


@router.post("/scan/abort", tags=["Scan"])
async def abort_scan():
    await get_orchestrator().emergency_abort()
    return {"ok": True, "aborted": True}
