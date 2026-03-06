from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import time
import re

router = APIRouter()


def _extract_imei_from_text(text: str):
    digits_only = re.sub(r"\D", "", text)
    match = re.search(r"\b\d{15}\b", digits_only)
    if match:
        return match.group(0)
    return None


def _read_single_frame(camera_index: int = 0):
    try:
        import cv2
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail="OpenCV (cv2) is not installed. Run `pip install -r requirements.txt`.",
        ) from e

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        raise HTTPException(
            status_code=500,
            detail=f"Could not open camera at index {camera_index}.",
        )

    try:
        ok, frame = cap.read()
        if not ok:
            raise HTTPException(status_code=500, detail="Could not read frame from camera.")
        return frame
    finally:
        cap.release()


def _mjpeg_stream(camera_index: int):
    try:
        import cv2
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail="OpenCV (cv2) is not installed. Run `pip install -r requirements.txt`.",
        ) from e

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        raise HTTPException(
            status_code=500,
            detail=f"Could not open camera at index {camera_index}.",
        )

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
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
    finally:
        cap.release()


@router.get("/camera/stream", tags=["Camera"])
def camera_stream(camera_index: int = 0):
    return StreamingResponse(
        _mjpeg_stream(camera_index),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/imei/detect", tags=["Camera"])
def detect_imei(camera_index: int = 0):
    try:
        from pyzbar.pyzbar import decode
        import cv2
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail="pyzbar is not installed. Install with `pip install pyzbar` and `sudo apt install libzbar0`.",
        ) from e

    frame = _read_single_frame(camera_index)
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