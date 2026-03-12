"""Scan orchestrator – runs the complete 65-step phone-grading sequence.

The orchestrator executes as a background asyncio.Task.  Every hardware step
broadcasts a WebSocket event so the frontend can track progress in real-time.

WebSocket event format:
    {
        "scan_event": {
            "type": "step_complete" | "step_error" | "scan_complete"
                   | "scan_failed" | "awaiting_user",
            "step": <int>,
            "step_name": "<str>",
            "data": { ... }
        }
    }
"""
from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException


@dataclass
class ScanSession:
    session_id: str
    imei: str
    device_model: str
    max_value_eur: float
    photo_paths: list[str] = field(default_factory=list)
    ai_result: Optional[dict] = None
    status: str = "running"      # running | awaiting_user | complete | failed
    current_step: int = 0
    error: Optional[str] = None


class ScanOrchestrator:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
        self.current_session: Optional[ScanSession] = None
        self._task: Optional[asyncio.Task] = None
        self._user_event: asyncio.Event = asyncio.Event()

    # ── Public API ────────────────────────────────────────────────────────────

    async def start_scan(
        self,
        imei: str,
        device_model: str,
        max_value_eur: float,
    ) -> ScanSession:
        if self.current_session and self.current_session.status == "running":
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
        """Called when user presses OK on an awaiting_user step."""
        self._user_event.set()

    async def emergency_abort(self):
        """Immediately stop all hardware and cancel the scan task."""
        if self._task and not self._task.done():
            self._task.cancel()

        await asyncio.to_thread(self._hw_emergency_stop)

        if self.current_session:
            self.current_session.status = "failed"
            self.current_session.error = "emergency_abort"

        await self._broadcast("scan_failed", 0, "emergency_abort", {"reason": "abort"})

    def get_status(self) -> Optional[dict]:
        if not self.current_session:
            return None
        s = self.current_session
        return {
            "session_id": s.session_id,
            "status": s.status,
            "current_step": s.current_step,
            "imei": s.imei,
            "device_model": s.device_model,
            "max_value_eur": s.max_value_eur,
            "photo_count": len(s.photo_paths),
            "ai_result": s.ai_result,
            "error": s.error,
        }

    # ── Hardware helpers (run via asyncio.to_thread) ──────────────────────────

    @staticmethod
    def _hw_emergency_stop():
        try:
            from services import machine_service, grbl_service
            machine_service.vacuum_off()
            machine_service.emergency_stop()
            grbl_service.feed_hold()
        except Exception:
            pass

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def _broadcast(
        self,
        event_type: str,
        step: int,
        step_name: str,
        data: dict,
    ):
        payload = {
            "scan_event": {
                "type": event_type,
                "step": step,
                "step_name": step_name,
                "data": data,
            }
        }
        try:
            await self.connection_manager.broadcast(payload)
        except Exception:
            pass  # never let a broadcast failure abort the sequence

    # ── Main sequence ─────────────────────────────────────────────────────────

    async def _run_sequence(self, session: ScanSession):
        try:
            await self._execute_sequence(session)
        except asyncio.CancelledError:
            session.status = "failed"
            session.error = "cancelled"
        except Exception as exc:
            session.status = "failed"
            session.error = str(exc)
            await self._broadcast("scan_failed", session.current_step, "error", {"error": str(exc)})
            await asyncio.to_thread(self._hw_emergency_stop)

    async def _step(self, session: ScanSession, step_num: int, step_name: str, fn, *args, **kwargs):
        """Run a blocking hardware function in a thread, update session, broadcast."""
        session.current_step = step_num
        result = await asyncio.to_thread(fn, *args, **kwargs)
        await self._broadcast("step_complete", step_num, step_name, result if isinstance(result, dict) else {})
        return result

    async def _await_user(self, session: ScanSession, step_num: int, step_name: str, message: str):
        """Pause sequence until user calls confirm_user_action()."""
        session.status = "awaiting_user"
        session.current_step = step_num
        self._user_event.clear()
        await self._broadcast("awaiting_user", step_num, step_name, {"message": message})
        timeout = float(os.getenv("APP_USER_CONFIRM_TIMEOUT_S", "300"))
        try:
            await asyncio.wait_for(self._user_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise Exception(f"User confirmation timeout at step {step_num}")
        session.status = "running"
        self._user_event.clear()

    async def _execute_sequence(self, session: ScanSession):
        from services import machine_service, grbl_service, ai_damage_service
        from controller.camera import take_photo, camera_manager

        vacuum_dwell = float(os.getenv("APP_VACUUM_DWELL_S", "1.0"))

        # ── Step 19: Gate open ────────────────────────────────────────────────
        await self._step(session, 19, "gate_open", machine_service.open_gate)
        await self._step(session, 19, "gate_open_wait", machine_service.wait_for_gate_done)

        # ── Step 20: Tray out ─────────────────────────────────────────────────
        await self._step(session, 20, "tray_out", machine_service.tray_out)
        await self._step(session, 20, "tray_out_wait", machine_service.wait_for_tray_done)

        # ── Step 21-22: Wait for user to add phone ────────────────────────────
        await self._await_user(session, 21, "phone_added_check", "Toestel toegevoegd?")

        # ── Step 23: Tray in (center) ─────────────────────────────────────────
        await self._step(session, 23, "tray_in", machine_service.tray_in)
        await self._step(session, 23, "tray_in_wait", machine_service.wait_for_tray_done)

        # ── Step 24: Gate close ───────────────────────────────────────────────
        await self._step(session, 24, "gate_close", machine_service.close_gate)
        await self._step(session, 24, "gate_close_wait", machine_service.wait_for_gate_done)

        # ── Step 25: Arm → front of phone (distance sensor stop) ─────────────
        await self._step(session, 25, "arm_approach_front",
                         grbl_service.move_to_front_slow_with_distance_stop)

        # ── Step 27: Vacuum ON ────────────────────────────────────────────────
        await self._step(session, 27, "vacuum_on", machine_service.vacuum_on)
        await asyncio.sleep(vacuum_dwell)

        # ── Step 28: Z up ─────────────────────────────────────────────────────
        await self._step(session, 28, "z_up", grbl_service.z_up)

        # ── Step 29: Tray to gate/camera position ─────────────────────────────
        await self._step(session, 29, "tray_to_gate", machine_service.tray_to_gate_position)
        await self._step(session, 29, "tray_to_gate_wait", machine_service.wait_for_tray_done)

        # ── Start camera if not already running ───────────────────────────────
        await asyncio.to_thread(camera_manager.start)

        # ── Step 30: Wrist 1: -90° → 0°  (write 90 = neutral) ────────────────
        await self._step(session, 30, "wrist1_neutral", machine_service.set_wrist1, 90)

        # ── Step 31: Photo front side 1 ───────────────────────────────────────
        result = await asyncio.to_thread(take_photo, "front_side_1", session.session_id)
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 31, "photo_front_side_1", result)

        # ── Step 32: Wrist 2: 0° → -90°  (write 0) ───────────────────────────
        await self._step(session, 32, "wrist2_neg90", machine_service.set_wrist2, 0)

        # ── Step 33: Photo front side 2 ───────────────────────────────────────
        result = await asyncio.to_thread(take_photo, "front_side_2", session.session_id)
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 33, "photo_front_side_2", result)

        # ── Step 34: Wrist 2: -90° → +90°  (write 180) ───────────────────────
        await self._step(session, 34, "wrist2_pos90", machine_service.set_wrist2, 180)

        # ── Step 35: Photo front side 3 ───────────────────────────────────────
        result = await asyncio.to_thread(take_photo, "front_side_3", session.session_id)
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 35, "photo_front_side_3", result)

        # ── Step 36: Wrist 1: 0° → +90°  (write 180) ────────────────────────
        await self._step(session, 36, "wrist1_pos90", machine_service.set_wrist1, 180)

        # ── Step 37: Tray back to center ──────────────────────────────────────
        await self._step(session, 37, "tray_center", machine_service.tray_in)
        await self._step(session, 37, "tray_center_wait", machine_service.wait_for_tray_done)

        # ── Step 38: Wrist home ────────────────────────────────────────────────
        await self._step(session, 38, "wrist_home", machine_service.wrist_home)

        # ── Step 39: Z down ───────────────────────────────────────────────────
        await self._step(session, 39, "z_down", grbl_service.z_down)

        # ── Step 40: Vacuum OFF ────────────────────────────────────────────────
        await self._step(session, 40, "vacuum_off", machine_service.vacuum_off)

        # ── Step 41: Arm → back of phone (rapid XY) ───────────────────────────
        await self._step(session, 41, "arm_to_back_rapid", grbl_service.move_to_back_of_phone)

        # ── Step 42: Slow approach with distance stop ──────────────────────────
        await self._step(session, 42, "arm_approach_back",
                         grbl_service.move_to_back_slow_with_distance_stop)

        # ── Step 43: Vacuum ON ────────────────────────────────────────────────
        await self._step(session, 43, "vacuum_on_back", machine_service.vacuum_on)
        await asyncio.sleep(vacuum_dwell)

        # ── Step 44: Z up ─────────────────────────────────────────────────────
        await self._step(session, 44, "z_up_back", grbl_service.z_up)

        # ── Step 45: Tray to gate/camera position ─────────────────────────────
        await self._step(session, 45, "tray_to_gate_back", machine_service.tray_to_gate_position)
        await self._step(session, 45, "tray_to_gate_back_wait", machine_service.wait_for_tray_done)

        # ── Step 46: Wrist 1 neutral ──────────────────────────────────────────
        await self._step(session, 46, "wrist1_neutral_back", machine_service.set_wrist1, 90)

        # ── Step 47: Photo back side 1 ────────────────────────────────────────
        result = await asyncio.to_thread(take_photo, "back_side_1", session.session_id)
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 47, "photo_back_side_1", result)

        # ── Step 48: Wrist 2: 0° → -90° ──────────────────────────────────────
        await self._step(session, 48, "wrist2_neg90_back", machine_service.set_wrist2, 0)

        # ── Step 49: Photo back side 2 ────────────────────────────────────────
        result = await asyncio.to_thread(take_photo, "back_side_2", session.session_id)
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 49, "photo_back_side_2", result)

        # ── Step 50: Wrist 2: -90° → +90° ────────────────────────────────────
        await self._step(session, 50, "wrist2_pos90_back", machine_service.set_wrist2, 180)

        # ── Step 51: Photo back side 3 ────────────────────────────────────────
        result = await asyncio.to_thread(take_photo, "back_side_3", session.session_id)
        session.photo_paths.append(result["path"])
        await self._broadcast("step_complete", 51, "photo_back_side_3", result)

        # ── Step 52: Wrist 1 +90° ─────────────────────────────────────────────
        await self._step(session, 52, "wrist1_pos90_back", machine_service.set_wrist1, 180)

        # ── Step 53: AI damage analysis ───────────────────────────────────────
        session.current_step = 53
        await self._broadcast("step_complete", 53, "ai_analyzing", {"photo_count": len(session.photo_paths)})
        ai_result = await asyncio.to_thread(
            ai_damage_service.analyze_photos,
            session.imei,
            session.session_id,
            session.photo_paths,
            session.max_value_eur,
        )
        session.ai_result = ai_result.model_dump()
        await self._broadcast("step_complete", 53, "ai_done", session.ai_result)

        # ── Step 54: Tray return center ───────────────────────────────────────
        await self._step(session, 54, "tray_center_back", machine_service.tray_in)
        await self._step(session, 54, "tray_center_back_wait", machine_service.wait_for_tray_done)

        # ── Step 55: Wrist home ────────────────────────────────────────────────
        await self._step(session, 55, "wrist_home_back", machine_service.wrist_home)

        # ── Step 56: Z down ───────────────────────────────────────────────────
        await self._step(session, 56, "z_down_back", grbl_service.z_down)

        # ── Step 57: Vacuum OFF ────────────────────────────────────────────────
        await self._step(session, 57, "vacuum_off_back", machine_service.vacuum_off)

        # ── Step 58: Gate open ────────────────────────────────────────────────
        await self._step(session, 58, "gate_open_return", machine_service.open_gate)
        await self._step(session, 58, "gate_open_return_wait", machine_service.wait_for_gate_done)

        # ── Step 59: Tray out ─────────────────────────────────────────────────
        await self._step(session, 59, "tray_out_return", machine_service.tray_out)
        await self._step(session, 59, "tray_out_return_wait", machine_service.wait_for_tray_done)

        # ── Step 60: Scan complete ────────────────────────────────────────────
        session.status = "complete"
        session.current_step = 60
        await self._broadcast("scan_complete", 60, "phone_retrieval", {"ai_result": session.ai_result})