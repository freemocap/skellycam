"""
WebSocket endpoint at /ws.
"""
import logging

from fastapi import APIRouter, WebSocket

from skellycam.api.websocket.websocket_server import WebsocketServer

logger = logging.getLogger(__name__)

websocket_router = APIRouter(tags=["WebSocket"])


@websocket_router.websocket("/ws")
async def websocket_connect(websocket: WebSocket):
    await websocket.accept()
    app = websocket.scope["app"]
    logger.success(f"WebSocket connection established at url: {websocket.url}")
    async with WebsocketServer(websocket=websocket, app=app) as ws_server:
        await ws_server.run()
    logger.info("WebSocket closed")
