from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

router = APIRouter()
PI_CAMERA_FULL_WIDTH = 4608
PI_CAMERA_FULL_HEIGHT = 2592
PI_CAMERA_JPEG_QUALITY = 95
PI_CAMERA_AF_TIMEOUT_S = 3.0
PI_CAMERA_STILL_TIMEOUT_EXTRA_S = 10.0
PI_CAMERA_FOCUS_RANGES = {"normal", "macro", "full"}

try:
    import cv2
except ModuleNotFoundError as exc:
    raise RuntimeError("OpenCV (cv2) is not installed.") from exc


class CameraManager:
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.thread = None
        self.running = False

    def start(self):
        if self.running:
            return
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            raise HTTPException(status_code=500, detail=f"Could not open camera at index {self.camera_index}.")
        self.running = True
        self.thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.thread.start()

    def _reader_loop(self):
        while self.running and self.cap is not None:
            ok, frame = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.05)

    def get_frame(self):
        if not self.running:
            self.start()
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def wait_for_frame(self, timeout_s: float = 5.0):
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            frame = self.get_frame()
            if frame is not None:
                return frame
            time.sleep(0.05)
        raise HTTPException(status_code=500, detail="Camera has no frame available.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        with self.lock:
            self.frame = None


def _get_camera_index() -> int:
    return int(os.getenv("APP_CAMERA_INDEX", "0"))


camera_manager = CameraManager(camera_index=_get_camera_index())


class CaptureRequest(BaseModel):
    label: str
    session_id: str


class PiCaptureRequest(BaseModel):
    imei: str = ""
    tag: str = "capture"
    width: int = Field(default=PI_CAMERA_FULL_WIDTH, ge=320, le=5000)
    height: int = Field(default=PI_CAMERA_FULL_HEIGHT, ge=240, le=5000)
    warmup_ms: int = Field(default=500, ge=0, le=5000)


class CameraSnapshotSaveRequest(BaseModel):
    tag: str = "camera_view"
    width: int = Field(default=PI_CAMERA_FULL_WIDTH, ge=320, le=5000)
    height: int = Field(default=PI_CAMERA_FULL_HEIGHT, ge=240, le=5000)
    warmup_ms: int = Field(default=500, ge=0, le=5000)


def _get_photo_storage_dir() -> Path:
    return Path(os.getenv("APP_PHOTO_STORAGE_DIR", "/tmp/sya_photos"))


def _get_pi_capture_dir() -> Path:
    configured = os.getenv("APP_PI_CAPTURE_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "data" / "captures"


def _get_camera_capture_dir() -> Path:
    configured = os.getenv("APP_CAMERA_CAPTURE_DIR", "").strip()
    if configured:
        return Path(configured)
    return _get_pi_capture_dir()


def _get_pi_camera_focus_range() -> str:
    focus_range = os.getenv("APP_PI_CAMERA_FOCUS_RANGE", "macro").strip().lower()
    return focus_range if focus_range in PI_CAMERA_FOCUS_RANGES else "macro"


def _safe_filename_part(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return normalized or fallback


def _wait_for_picamera_job(picam2, job) -> None:
    if job is None:
        return
    if hasattr(picam2, "wait"):
        try:
            picam2.wait(job, timeout=PI_CAMERA_AF_TIMEOUT_S)
            return
        except TypeError:
            picam2.wait(job)
            return
    if hasattr(job, "wait"):
        try:
            job.wait(timeout=PI_CAMERA_AF_TIMEOUT_S)
        except TypeError:
            job.wait()


def _run_pi_autofocus_cycle(picam2, controls_module) -> None:
    try:
        picam2.set_controls({"AfMode": controls_module.AfModeEnum.Auto})
    except Exception:
        pass

    focus_range_enum = getattr(controls_module, "AfRangeEnum", None)
    if focus_range_enum is not None:
        enum_name = _get_pi_camera_focus_range().capitalize()
        enum_value = getattr(focus_range_enum, enum_name, None)
        if enum_value is not None:
            try:
                picam2.set_controls({"AfRange": enum_value})
            except Exception:
                pass

    autofocus_cycle = getattr(picam2, "autofocus_cycle", None)
    if callable(autofocus_cycle):
        for kwargs in ({"wait": True}, {}):
            try:
                job = autofocus_cycle(**kwargs)
                if not kwargs.get("wait"):
                    _wait_for_picamera_job(picam2, job)
                return
            except TypeError:
                continue
            except Exception:
                return

    try:
        picam2.set_controls({"AfTrigger": controls_module.AfTriggerEnum.Start})
        time.sleep(min(PI_CAMERA_AF_TIMEOUT_S, 1.0))
    except Exception:
        pass


def _capture_pi_csi_frame(width: int, height: int, warmup_ms: int):
    try:
        from picamera2 import Picamera2  # type: ignore
        from libcamera import controls  # type: ignore
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="Picamera2/libcamera is not installed. On Raspberry Pi install with `sudo apt install -y python3-picamera2`.",
        ) from exc

    picam2 = None
    try:
        picam2 = Picamera2()
        config = picam2.create_still_configuration(main={"size": (width, height)})
        picam2.configure(config)
        picam2.start()
        if warmup_ms > 0:
            time.sleep(warmup_ms / 1000.0)

        _run_pi_autofocus_cycle(picam2, controls)
        return picam2.capture_array("main")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to capture CSI camera frame: {exc}") from exc
    finally:
        if picam2 is not None:
            try:
                picam2.stop()
            except Exception:
                pass
            try:
                picam2.close()
            except Exception:
                pass


def _get_pi_still_command() -> str:
    configured = os.getenv("APP_PI_STILL_COMMAND", "").strip()
    if configured:
        return configured
    for command in ("libcamera-still", "rpicam-still"):
        resolved = shutil.which(command)
        if resolved:
            return resolved
    raise HTTPException(
        status_code=500,
        detail="No Pi camera still command found. Install libcamera/rpicam tools or set APP_PI_STILL_COMMAND.",
    )


def _capture_pi_still_jpeg(width: int, height: int, warmup_ms: int) -> bytes:
    command = _get_pi_still_command()
    focus_range = _get_pi_camera_focus_range()
    timeout_ms = max(warmup_ms, 2000)
    base_command = [
        command,
        "--nopreview",
        "--output",
        "-",
        "--width",
        str(width),
        "--height",
        str(height),
        "--quality",
        str(PI_CAMERA_JPEG_QUALITY),
        "--timeout",
        str(timeout_ms),
    ]

    focus_candidates = (
        ["--autofocus-mode", "auto", "--autofocus-range", focus_range, "--autofocus-on-capture"],
        ["--autofocus-on-capture", "--autofocus-range", focus_range],
        ["--autofocus-mode", "auto", "--autofocus-range", focus_range],
        ["--autofocus-range", focus_range],
        [],
    )

    for focus_options in focus_candidates:
        candidate = base_command + focus_options
        try:
            completed = subprocess.run(
                candidate,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=(timeout_ms / 1000.0) + PI_CAMERA_STILL_TIMEOUT_EXTRA_S,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail=f"Pi camera still command timed out: {command}") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to run Pi camera still command: {exc}") from exc

        if completed.returncode == 0 and completed.stdout:
            return completed.stdout

        stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
        lowered_stderr = stderr.lower()
        if focus_options and (
            "ambiguous" in lowered_stderr
            or "unrecognised option" in lowered_stderr
            or "unrecognized option" in lowered_stderr
        ):
            continue

        raise HTTPException(
            status_code=500,
            detail=f"Pi camera still command failed: {stderr or 'no output'}",
        )

    raise HTTPException(status_code=500, detail="Pi camera still command failed.")


def _capture_pi_csi_jpeg(width: int, height: int, warmup_ms: int) -> bytes:
    picamera_error = None
    try:
        frame = _capture_pi_csi_frame(width, height, warmup_ms)
        return _encode_jpeg(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    except HTTPException as exc:
        picamera_error = exc.detail

    try:
        return _capture_pi_still_jpeg(width, height, warmup_ms)
    except HTTPException as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "picamera2": picamera_error,
                "still_command": exc.detail,
            },
        ) from exc


def _extract_imei_from_text(text: str):
    digits_only = re.sub(r"\D", "", text)
    match = re.search(r"\d{15}", digits_only)
    if match:
        return match.group(0)
    return None


def _mjpeg_stream():
    while True:
        frame = camera_manager.get_frame()
        if frame is None:
            time.sleep(0.05)
            continue
        ok, jpg = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        payload = jpg.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8")
            + payload
            + b"\r\n"
        )


@router.get("/camera/stream", tags=["Camera"])
def camera_stream():
    camera_manager.start()
    return StreamingResponse(_mjpeg_stream(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/imei/detect", tags=["Camera"])
def detect_imei():
    try:
        from pyzbar.pyzbar import decode
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="pyzbar is not installed. Install with `pip install pyzbar` and `sudo apt install libzbar0`.",
        ) from exc

    frame = camera_manager.get_frame()
    if frame is None:
        return {"found": False, "detail": "No frame available yet."}
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    decoded_objects = decode(gray) or decode(frame)
    for obj in decoded_objects:
        try:
            raw_text = obj.data.decode("utf-8")
        except Exception:
            continue
        imei = _extract_imei_from_text(raw_text)
        if imei:
            return {"found": True, "imei": imei, "raw": raw_text, "type": obj.type}
    return {"found": False}


def take_photo(label: str, session_id: str) -> dict:
    frame = camera_manager.wait_for_frame()
    session_dir = _get_photo_storage_dir() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    file_path = session_dir / f"{label}.jpg"
    ok, jpg = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode camera frame as JPEG.")
    file_path.write_bytes(jpg.tobytes())
    return {"path": str(file_path), "label": label, "session_id": session_id}


def _encode_jpeg(frame) -> bytes:
    ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), PI_CAMERA_JPEG_QUALITY])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode camera frame as JPEG.")
    return jpg.tobytes()


def _encode_jpeg_response(frame) -> Response:
    return Response(
        content=_encode_jpeg(frame),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/camera/snapshot/{source}", tags=["Camera"])
def camera_snapshot(
    source: str,
    width: int = Query(default=PI_CAMERA_FULL_WIDTH, ge=320, le=5000),
    height: int = Query(default=PI_CAMERA_FULL_HEIGHT, ge=240, le=5000),
    warmup_ms: int = Query(default=500, ge=0, le=5000),
):
    normalized = source.strip().lower()
    if normalized == "usb":
        camera_manager.start()
        return _encode_jpeg_response(camera_manager.wait_for_frame())
    if normalized == "pi":
        return Response(
            content=_capture_pi_csi_jpeg(width, height, warmup_ms),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )
    raise HTTPException(status_code=400, detail="Unknown camera source. Use 'usb' or 'pi'.")


@router.post("/camera/snapshot/{source}/save", tags=["Camera"])
def save_camera_snapshot(source: str, payload: CameraSnapshotSaveRequest):
    normalized = source.strip().lower()
    if normalized == "usb":
        camera_manager.start()
        jpeg_bytes = _encode_jpeg(camera_manager.wait_for_frame())
    elif normalized == "pi":
        jpeg_bytes = _capture_pi_csi_jpeg(payload.width, payload.height, payload.warmup_ms)
    else:
        raise HTTPException(status_code=400, detail="Unknown camera source. Use 'usb' or 'pi'.")

    capture_dir = _get_camera_capture_dir()
    capture_dir.mkdir(parents=True, exist_ok=True)
    source_part = _safe_filename_part(normalized, "camera")
    tag_part = _safe_filename_part(payload.tag, "camera_view")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{timestamp}_{source_part}_{tag_part}.jpg"
    file_path = capture_dir / filename
    file_path.write_bytes(jpeg_bytes)
    return {
        "saved": True,
        "source": normalized,
        "tag": payload.tag,
        "filename": filename,
        "path": str(file_path),
    }


@router.post("/camera/capture", tags=["Camera"])
def capture_photo(payload: CaptureRequest):
    camera_manager.start()
    return take_photo(payload.label, payload.session_id)


@router.post("/camera/pi/capture", tags=["Camera"])
def capture_pi_camera_photo(payload: PiCaptureRequest):
    capture_dir = _get_pi_capture_dir()
    capture_dir.mkdir(parents=True, exist_ok=True)
    imei_part = _safe_filename_part(payload.imei, "no_imei")
    tag_part = _safe_filename_part(payload.tag, "capture")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{timestamp}_{imei_part}_{tag_part}.jpg"
    file_path = capture_dir / filename
    file_path.write_bytes(_capture_pi_csi_jpeg(payload.width, payload.height, payload.warmup_ms))
    return {"saved": True, "filename": filename, "path": str(file_path), "imei": payload.imei, "tag": payload.tag}
