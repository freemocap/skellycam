import logging

from fastapi import APIRouter, WebSocket

from skellycam.api.websocket.connect.websocket_server import WebsocketServer

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


@websocket_router.websocket("/connect")
async def websocket_server_connect(websocket: WebSocket):
    """
    Websocket endpoint for client connection to the server - handles image data streaming to frontend.
    """

    await websocket.accept()
    logger.success(f"Websocket connection established!")

    async with WebsocketServer(websocket=websocket) as websocket_server:
        set_websocket_server(websocket_server)
        await websocket_server.run()
    logger.info("Websocket closed")

WEBSOCKET_SERVER : WebsocketServer|None = None

def set_websocket_server(websocket_server:WebsocketServer):
    global WEBSOCKET_SERVER
    WEBSOCKET_SERVER = websocket_server

def get_websocket_server() -> WebsocketServer:
    global WEBSOCKET_SERVER
    return WEBSOCKET_SERVER