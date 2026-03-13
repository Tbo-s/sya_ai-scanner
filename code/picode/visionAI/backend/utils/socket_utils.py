import json

from fastapi import WebSocket, WebSocketDisconnect
from typing import Any, List


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: Any):
        text = data if isinstance(data, str) else json.dumps(data)
        dead: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(text)
            except (WebSocketDisconnect, Exception):
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


connection_manager = ConnectionManager()
