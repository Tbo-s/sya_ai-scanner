import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from controller.notes import router as party_router
from controller.camera import router as camera_router
from controller.arduino import router as arduino_router
from controller.device_lookup import router as device_lookup_router
from controller.ai_damage import router as ai_damage_router
from controller.scan import router as scan_router, set_orchestrator

from utils.socket_utils import connection_manager
from services.scan_orchestrator import ScanOrchestrator
from init import init

PORT = 3000

# ── FastAPI app ───────────────────────────────────────────────────────────────
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
app.include_router(ai_damage_router, prefix="/api")
app.include_router(scan_router, prefix="/api")


# ── Alive check ───────────────────────────────────────────────────────────────
@app.get("/api")
async def alive():
    return {"status": "alive"}


# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await connection_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                msg = {}

            # Forward user confirmation to the scan orchestrator
            if msg.get("action") == "confirm":
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


# ── Serve Vue SPA in production ───────────────────────────────────────────────
try:
    build_dir = Path(__file__).resolve().parent / "dist"
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


# ── Startup: wire up the scan orchestrator ────────────────────────────────────
orchestrator = ScanOrchestrator(connection_manager)
set_orchestrator(orchestrator)

init()

print("\nRunning FastAPI app...")
print(" - FastAPI is available at " + f"http://localhost:{PORT}/api")
print(" - Swagger UI is available at " + f"http://localhost:{PORT}/docs")
print(" - Redoc is available at " + f"http://localhost:{PORT}/redoc")
print("")
