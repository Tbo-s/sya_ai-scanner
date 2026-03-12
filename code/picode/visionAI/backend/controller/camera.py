from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import time
import re
import threading
import os
from datetime import datetime
from pathlib import Path

router = APIRouter()

try:
    import cv2
except ModuleNotFoundError as e:
    raise RuntimeError("OpenCV (cv2) is not installed.") from e


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
            raise HTTPException(
                status_code=500,
                detail=f"Could not open camera at index {self.camera_index}.",
            )

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


camera_manager = CameraManager(camera_index=0)


class PiCaptureRequest(BaseModel):
    imei: str = ""
    tag: str = "capture"
    width: int = Field(default=1920, ge=320, le=5000)
    height: int = Field(default=1080, ge=240, le=5000)
    warmup_ms: int = Field(default=300, ge=0, le=5000)


def _get_pi_capture_dir() -> Path:
    default_path = Path(__file__).resolve().parent.parent / "data" / "captures"
    configured = os.getenv("APP_PI_CAPTURE_DIR", "").strip()
    return Path(configured) if configured else default_path


def _safe_filename_part(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    normalized = normalized.strip("_")
    return normalized or fallback


def _capture_pi_csi_frame(width: int, height: int, warmup_ms: int):
    try:
        from picamera2 import Picamera2  # type: ignore
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=(
                "Picamera2 is not installed. On Raspberry Pi install with: "
                "`sudo apt install -y python3-picamera2`."
            ),
        ) from e

    picam2 = None
    try:
        picam2 = Picamera2()
        config = picam2.create_still_configuration(main={"size": (width, height)})
        picam2.configure(config)
        picam2.start()
        if warmup_ms > 0:
            time.sleep(warmup_ms / 1000.0)
        frame = picam2.capture_array("main")
        return frame
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to capture CSI camera frame: {e}") from e
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
    return StreamingResponse(
        _mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/imei/detect", tags=["Camera"])
def detect_imei():
    try:
        from pyzbar.pyzbar import decode
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail="pyzbar is not installed. Install with `pip install pyzbar` and `sudo apt install libzbar0`.",
        ) from e

    frame = camera_manager.get_frame()
    if frame is None:
        return {"found": False, "detail": "No frame available yet."}

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    decoded_objects = decode(gray)
    if not decoded_objects:
        decoded_objects = decode(frame)

    for obj in decoded_objects:
        try:
            raw_text = obj.data.decode("utf-8")
        except Exception:
            continue

        imei = _extract_imei_from_text(raw_text)
        if imei:
            return {
                "found": True,
                "imei": imei,
                "raw": raw_text,
                "type": obj.type,
            }

    return {"found": False}


@router.post("/camera/pi/capture", tags=["Camera"])
def capture_pi_camera_photo(payload: PiCaptureRequest):
    frame = _capture_pi_csi_frame(
        width=payload.width,
        height=payload.height,
        warmup_ms=payload.warmup_ms,
    )

    # Picamera2 returns RGB by default; convert so saved file colors are correct.
    bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    capture_dir = _get_pi_capture_dir()
    capture_dir.mkdir(parents=True, exist_ok=True)

    imei_part = _safe_filename_part(payload.imei, "no_imei")
    tag_part = _safe_filename_part(payload.tag, "capture")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{timestamp}_{imei_part}_{tag_part}.jpg"
    file_path = capture_dir / filename

    ok = cv2.imwrite(str(file_path), bgr)
    if not ok:
        raise HTTPException(status_code=500, detail=f"Failed to save capture to {file_path}")

    return {
        "saved": True,
        "filename": filename,
        "path": str(file_path),
        "imei": payload.imei,
        "tag": payload.tag,
    }
