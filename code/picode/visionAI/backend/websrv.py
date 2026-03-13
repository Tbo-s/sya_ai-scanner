import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from controller.arduino import router as arduino_router
from controller.camera import router as camera_router
from controller.device_lookup import router as device_lookup_router
from controller.notes import router as party_router
from controller.scan import router as scan_router, set_orchestrator
from controller.system import router as system_router
from init import init
from services.scan_orchestrator import ScanOrchestrator
from services.system_service import boot_initialize
from utils.socket_utils import connection_manager

PORT = 3000

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(party_router, prefix="/api")
app.include_router(camera_router, prefix="/api")
app.include_router(arduino_router, prefix="/api")
app.include_router(device_lookup_router, prefix="/api")
app.include_router(scan_router, prefix="/api")
app.include_router(system_router, prefix="/api")


@app.get("/api")
async def alive():
    return {"status": "alive"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await connection_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except Exception:
                payload = {}

            if payload.get("action") == "confirm":
                from controller.scan import get_orchestrator

                try:
                    await get_orchestrator().confirm_user_action()
                except Exception:
                    pass
            else:
                await connection_manager.broadcast({"message": f"Message text was: {data}"})
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        await connection_manager.broadcast({"message": "A client just disconnected."})


try:
    configured_dist = os.getenv("APP_FRONTEND_DIST", "").strip()
    if configured_dist:
        build_dir = Path(configured_dist)
    else:
        backend_dir = Path(__file__).resolve().parent / "dist"
        frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
        build_dir = frontend_dir if frontend_dir.exists() else backend_dir
    index_path = build_dir / "index.html"
    app.mount("/assets", StaticFiles(directory=build_dir / "assets"), name="assets")

    @app.get("/{catchall:path}")
    async def serve_spa(catchall: str):
        path = build_dir / catchall
        if path.is_file():
            return FileResponse(path)
        return FileResponse(index_path)

except RuntimeError:
    print("No build directory found. Running in development mode.")


orchestrator = ScanOrchestrator(connection_manager)
set_orchestrator(orchestrator)

init()
boot_report = boot_initialize()
if not boot_report.get("ok"):
    print("Machine boot initialization completed with warnings:")
    for entry in boot_report.get("errors", []):
        print(" -", entry["step"] + ":", entry["error"])
else:
    print("Machine boot initialization OK.")

print("\nRunning FastAPI app...")
print(" - FastAPI is available at " + f"http://localhost:{PORT}/api")
print(" - Swagger UI is available at " + f"http://localhost:{PORT}/docs")
print(" - Redoc is available at " + f"http://localhost:{PORT}/redoc")
print("")
