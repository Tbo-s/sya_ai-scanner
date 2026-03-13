from fastapi import APIRouter

from services import system_service

router = APIRouter()


@router.get("/system/settings", tags=["System"])
def system_settings():
    return system_service.get_runtime_settings()


@router.post("/system/safe-idle", tags=["System"])
def system_safe_idle():
    return system_service.safe_idle_state()


@router.post("/system/home", tags=["System"])
def system_home():
    return system_service.home_axes()


@router.get("/system/boot-report", tags=["System"])
def system_boot_report():
    return system_service.boot_initialize()
