from fastapi import APIRouter
from pydantic import BaseModel

from services.inspection_service import build_inspection_plan, execute_inspection_plan
from services.inspection_state_machine_service import (
    build_inspection_state_machine_definition,
    run_inspection_state_machine,
)


router = APIRouter()


class InspectionRequest(BaseModel):
    imei: str = ""
    model: str = ""
    max_value_eur: float = 0.0
    dry_run: bool = True
    trigger_emergency_stop: bool = False


@router.get("/inspection/definition", tags=["Inspection"])
def inspection_definition():
    return build_inspection_plan()


@router.post("/inspection/plan", tags=["Inspection"])
def inspection_plan(payload: InspectionRequest):
    return build_inspection_plan(
        imei=payload.imei,
        model=payload.model,
        max_value_eur=payload.max_value_eur,
    )


@router.post("/inspection/run", tags=["Inspection"])
def inspection_run(payload: InspectionRequest):
    return execute_inspection_plan(
        imei=payload.imei,
        model=payload.model,
        max_value_eur=payload.max_value_eur,
        dry_run=payload.dry_run,
    )


@router.get("/inspection/state-machine/definition", tags=["Inspection"])
def inspection_state_machine_definition():
    return build_inspection_state_machine_definition()


@router.post("/inspection/state-machine/run", tags=["Inspection"])
def inspection_state_machine_run(payload: InspectionRequest):
    return run_inspection_state_machine(
        imei=payload.imei,
        model=payload.model,
        max_value_eur=payload.max_value_eur,
        dry_run=payload.dry_run,
        trigger_emergency_stop=payload.trigger_emergency_stop,
    )
