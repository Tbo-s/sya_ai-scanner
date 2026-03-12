from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import time
import re
import threading
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


def _get_camera_index() -> int:
    return int(os.getenv("APP_CAMERA_INDEX", "0"))


camera_manager = CameraManager(camera_index=_get_camera_index())


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


# ── Photo capture ─────────────────────────────────────────────────────────────

class CaptureRequest(BaseModel):
    label: str
    session_id: str


def take_photo(label: str, session_id: str) -> dict:
    """Capture a single frame and save it to disk.  Returns the file path."""
    frame = camera_manager.get_frame()
    if frame is None:
        raise HTTPException(status_code=500, detail="Camera has no frame available.")

    storage_dir = os.getenv("APP_PHOTO_STORAGE_DIR", "/tmp/sya_photos")
    session_dir = Path(storage_dir) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{label}.jpg"
    filepath = session_dir / filename

    ok, jpg = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode camera frame as JPEG.")

    filepath.write_bytes(jpg.tobytes())
    return {"path": str(filepath), "label": label, "session_id": session_id}


@router.post("/camera/capture", tags=["Camera"])
def capture_photo(payload: CaptureRequest):
    camera_manager.start()
    return take_photo(payload.label, payload.session_id)