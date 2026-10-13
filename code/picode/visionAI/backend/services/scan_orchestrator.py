from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException


class FlowState:
    BOOT = "BOOT"
    WELCOME = "WELCOME"
    IMEI_SCAN = "IMEI_SCAN"
    DEVICE_LOOKUP = "DEVICE_LOOKUP"
    WAIT_POWER_OFF = "WAIT_POWER_OFF"
    LOAD_DEVICE = "LOAD_DEVICE"
    CLOSE_BOX = "CLOSE_BOX"
    CAPTURE_FRONT = "CAPTURE_FRONT"
    CAPTURE_BACK = "CAPTURE_BACK"
    UPLOAD_RESULTS = "UPLOAD_RESULTS"
    RETURN_DEVICE = "RETURN_DEVICE"
    SHOW_PRICE = "SHOW_PRICE"
    DONE = "DONE"
    ERROR = "ERROR"
    EMERGENCY_STOP = "EMERGENCY_STOP"


@dataclass
class ScanSession:
    session_id: str
    imei: str
    device_model: str
    max_value_eur: float
    photo_paths: list[str] = field(default_factory=list)
    ai_result: Optional[dict] = None
    upload_result: Optional[dict] = None
    status: str = "running"
    state: str = FlowState.LOAD_DEVICE
    current_step: int = 0
    error: Optional[str] = None


class ScanOrchestrator:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
        self.current_session: Optional[ScanSession] = None
        self._task: Optional[asyncio.Task] = None
        self._user_event = asyncio.Event()

    async def start_scan(self, imei: str, device_model: str, max_value_eur: float) -> ScanSession:
        if self._task and not self._task.done():
            raise HTTPException(status_code=409, detail="A scan is already in progress.")

        session = ScanSession(
            session_id=str(uuid.uuid4()),
            imei=imei,
            device_model=device_model,
            max_value_eur=max_value_eur,
        )
        self.current_session = session
        self._user_event.clear()
        self._task = asyncio.create_task(self._run_sequence(session))
        return session

    async def confirm_user_action(self):
        if not self.current_session or self.current_session.status != "awaiting_user":
            raise HTTPException(status_code=409, detail="No scan is waiting for confirmation.")
        self._user_event.set()

    async def emergency_abort(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await asyncio.to_thread(self._hw_emergency_stop)
        if self.current_session:
            self.current_session.status = "failed"
            self.current_session.state = FlowState.EMERGENCY_STOP
            self.current_session.error = "emergency_abort"
        await self._broadcast(
            "scan_failed",
            0,
            "emergency_abort",
            {"reason": "abort"},
            state=FlowState.EMERGENCY_STOP,
        )

    def get_status(self) -> Optional[dict]:
        if not self.current_session:
            return None
        session = self.current_session
        return {
            "session_id": session.session_id,
            "status": session.status,
            "state": session.state,
            "current_step": session.current_step,
            "imei": session.imei,
            "device_model": session.device_model,
            "max_value_eur": session.max_value_eur,
            "photo_count": len(session.photo_paths),
            "ai_result": session.ai_result,
            "upload_result": session.upload_result,
            "error": session.error,
        }

    @staticmethod
    def _hw_emergency_stop():
        try:
            from services import grbl_service, machine_service

            machine_service.vacuum_off(raise_on_no_ack=False)
            machine_service.emergency_stop()
            grbl_service.feed_hold()
        except Exception:
            pass

    async def _broadcast(
        self,
        event_type: str,
        step: int,
        step_name: str,
        data: dict,
        state: Optional[str] = None,
    ):
        current_state = state or (self.current_session.state if self.current_session else "")
        payload = {
            "scan_event": {
                "type": event_type,
                "state": current_state,
                "step": step,
                "step_name": step_name,
                "data": {"state": current_state, **data},
            }
        }
        try:
            await self.connection_manager.broadcast(payload)
        except Exception:
            pass

    async def _run_sequence(self, session: ScanSession):
        try:
            await self._execute_sequence(session)
        except asyncio.CancelledError:
            session.status = "failed"
            session.state = FlowState.ERROR
            session.error = "cancelled"
            raise
        except Exception as exc:
            session.status = "failed"
            session.state = FlowState.ERROR
            session.error = str(exc)
            await self._broadcast(
                "scan_failed",
                session.current_step,
                "error",
                {"error": str(exc)},
                state=FlowState.ERROR,
            )
            await asyncio.to_thread(self._hw_emergency_stop)

    async def _set_state(self, session: ScanSession, state: str, data: Optional[dict] = None):
        session.state = state
        await self._broadcast("state_changed", session.current_step, state.lower(), data or {}, state=state)

    async def _step(self, session: ScanSession, step_num: int, step_name: str, fn, *args, **kwargs):
        session.current_step = step_num
        result = await asyncio.to_thread(fn, *args, **kwargs)
        await self._broadcast("step_complete", step_num, step_name, result if isinstance(result, dict) else {})
        return result

    async def _await_user(self, session: ScanSession, step_num: int, step_name: str, message: str):
        session.status = "awaiting_user"
        session.current_step = step_num
        self._user_event.clear()
        await self._broadcast("awaiting_user", step_num, step_name, {"message": message}, state=session.state)
        timeout = float(os.getenv("APP_USER_CONFIRM_TIMEOUT_S", "300"))
        try:
            await asyncio.wait_for(self._user_event.wait(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise RuntimeError(f"User confirmation timeout at step {step_num}") from exc
        session.status = "running"
        self._user_event.clear()

    async def _execute_sequence(self, session: ScanSession):
        from controller.camera import camera_manager, take_photo, take_pi_photo
        from services import grbl_service, machine_service
        from services.wrist_preset_service import get_wrist_presets

        await self._set_state(session, FlowState.LOAD_DEVICE)
        await self._step(session, 19, "gate_open", machine_service.open_gate)
        await self._step(session, 19, "gate_open_wait", machine_service.wait_for_gate_done)
        await self._step(session, 20, "tray_out", machine_service.tray_out)
        await self._step(session, 20, "tray_out_wait", machine_service.wait_for_tray_done)
        await self._await_user(session, 21, "phone_added_check", "Toestel toegevoegd?")

        await self._set_state(session, FlowState.CLOSE_BOX)
        await self._step(session, 23, "tray_in", machine_service.tray_in)
        await self._step(session, 23, "tray_in_wait", machine_service.wait_for_tray_done)
        await self._step(session, 24, "gate_close", machine_service.close_gate)
        await self._step(session, 24, "gate_close_wait", machine_service.wait_for_gate_done)

        await self._set_state(session, FlowState.CAPTURE_FRONT)
        presets = {
            wrist_key: {preset["key"]: int(preset["logical"]) for preset in values}
            for wrist_key, values in get_wrist_presets().items()
        }
        wrist1_camera = presets["wrist1"]["camera"]
        wrist1_wall = presets["wrist1"]["wall"]
        wrist2_horizontal = presets["wrist2"]["horizontal"]
        wrist2_vertical_left = presets["wrist2"]["vertical_left"]
        wrist2_vertical_right = presets["wrist2"]["vertical_right"]
        scan_feed_rate = int(os.getenv("APP_GRBL_AUTO_SCAN_FEED_RATE", "1500"))
        start_x = float(os.getenv("APP_GRBL_SCAN_START_X", "2.8"))
        start_y = float(os.getenv("APP_GRBL_SCAN_START_Y", "0.6"))
        vacuum_off_y = float(os.getenv("APP_GRBL_SCAN_VACUUM_OFF_Y", "0.8"))
        vacuum_hold_s = max(0.0, float(os.getenv("APP_GRBL_SCAN_VACUUM_HOLD_S", "2.0")))
        photo_y = float(os.getenv("APP_GRBL_SCAN_PHOTO_Y", "2.0"))
        second_photo_x = float(os.getenv("APP_GRBL_SCAN_SECOND_PHOTO_X", "4.0"))
        z_lift = float(os.getenv("APP_GRBL_SCAN_Z_LIFT", "6.0"))
        camera_source = os.getenv("APP_SCAN_CAMERA_SOURCE", "pi").strip().lower()
        if camera_source not in {"pi", "usb"}:
            raise RuntimeError("APP_SCAN_CAMERA_SOURCE must be 'pi' or 'usb'.")

        async def capture_scan_photo(label: str) -> dict:
            if camera_source == "pi":
                return await asyncio.to_thread(take_pi_photo, label, session.session_id)
            return await asyncio.to_thread(take_photo, label, session.session_id)

        await self._step(session, 25, "arm_x_start", grbl_service.move_axis_absolute, "X", start_x, "scan_x_start", scan_feed_rate)
        await self._step(session, 26, "wrist1_camera", machine_service.set_wrist1, wrist1_camera)
        await self._step(session, 27, "wrist2_horizontal", machine_service.set_wrist2, wrist2_horizontal)
        await self._step(session, 28, "arm_y_start", grbl_service.move_axis_absolute, "Y", start_y, "scan_y_start", scan_feed_rate)
        await self._step(session, 29, "vacuum1_on", machine_service.set_vacuum1_motor, True)
        await self._step(session, 30, "vacuum2_on", machine_service.set_vacuum2_motor, True)
        await self._step(session, 31, "arm_y_vacuum_off", grbl_service.move_axis_absolute, "Y", vacuum_off_y, "scan_y_vacuum_off", scan_feed_rate)
        await asyncio.sleep(vacuum_hold_s)
        await self._step(session, 32, "vacuum1_off", machine_service.set_vacuum1_motor, False)
        await self._step(session, 33, "vacuum2_off", machine_service.set_vacuum2_motor, False)
        await self._step(session, 34, "arm_z_lift", grbl_service.move_z_relative, z_lift, "scan_z_lift", scan_feed_rate)
        await self._step(session, 35, "arm_y_photo", grbl_service.move_axis_absolute, "Y", photo_y, "scan_y_photo", scan_feed_rate)

        if camera_source == "usb":
            await asyncio.to_thread(camera_manager.start)
            await asyncio.to_thread(camera_manager.wait_for_frame, 5.0)

        result = await capture_scan_photo("photo_1")
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 36, "photo_1", result)

        await self._step(session, 37, "wrist1_wall", machine_service.set_wrist1, wrist1_wall)
        await self._step(session, 38, "arm_x_photo_2", grbl_service.move_axis_absolute, "X", second_photo_x, "scan_x_photo_2", scan_feed_rate)
        result = await capture_scan_photo("photo_2")
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 39, "photo_2", result)
        await self._step(session, 40, "wrist2_vertical_left", machine_service.set_wrist2, wrist2_vertical_left)
        result = await capture_scan_photo("photo_3")
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 41, "photo_3", result)
        await self._step(session, 42, "wrist2_vertical_right", machine_service.set_wrist2, wrist2_vertical_right)
        result = await capture_scan_photo("photo_4")
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 43, "photo_4", result)

        session.status = "complete"
        session.state = FlowState.SHOW_PRICE
        session.current_step = 44
        await self._broadcast(
            "scan_complete",
            44,
            "capture_complete",
            {"ai_result": None, "photo_count": len(session.photo_paths)},
            state=FlowState.SHOW_PRICE,
        )
