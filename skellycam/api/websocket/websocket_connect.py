import logging

from fastapi import APIRouter, WebSocket

from skellycam.api.websocket.websocket_server import WebsocketServer

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

HELLO_CLIENT_TEXT_MESSAGE = "👋Hello, websocket client!"
HELLO_CLIENT_JSON_MESSAGE = {"message": "hey wow im json!"}


@websocket_router.websocket("/connect")
async def websocket_server_connect(websocket: WebSocket):
    """
    Websocket endpoint for client connection to the server - handles image data streaming to frontend.
    """

    await websocket.accept()
    await websocket.send_text(HELLO_CLIENT_TEXT_MESSAGE)
    await websocket.send_json(HELLO_CLIENT_JSON_MESSAGE)
    logger.success(f"Websocket connection established!")

    async with WebsocketServer(websocket=websocket) as runner:
        await runner.run()
    logger.info("Websocket closed")
