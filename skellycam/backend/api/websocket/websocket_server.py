import logging

from fastapi import APIRouter, WebSocket

from skellycam.backend.core.controller.singleton import get_or_create_controller

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


async def listen_for_client_messages(websocket: WebSocket):
    logger.info("Starting listener for client messages...")
    while True:
        try:
            message = await websocket.receive_text()
            logger.debug(f"Message from client: '{message}'")

            if not message:
                logger.api("Empty message received, ending listener task...")
                break

        except Exception as e:
            logger.error(f"Error while receiving message: {type(e).__name__} - {e}")
            break


class WebsocketRunner:
    async def __aenter__(self):
        logger.api("WebsocketRunner started...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.api("WebsocketRunner ended...")
        pass


@websocket_router.websocket("/ws/connect")
async def websocket_server_connect(websocket: WebSocket):
    logger.success(f"Websocket connection established!")

    await websocket.accept()
    await websocket.send_text("Hello, client!")

    async def websocket_send_bytes(data: bytes):
        await websocket.send_bytes(data)

    controller = get_or_create_controller()
    controller.set_websocket_bytes_sender(websocket_send_bytes)

    async with WebsocketRunner():
        try:
            logger.api("Creating listener task...")
            await listen_for_client_messages(websocket)

        except Exception as e:
            logger.exception(e)
            logger.error(f"Error while running camera loop: {type(e).__name__}- {e}")
        finally:
            logger.api("Websocket ended")
            await websocket.close()
            logger.api("Websocket closed")
