from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import time


router = APIRouter()


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
