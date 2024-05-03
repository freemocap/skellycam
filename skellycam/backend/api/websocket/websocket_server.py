import asyncio
import logging

from fastapi import APIRouter, WebSocket

from skellycam.backend.core.controller import Controller

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


async def listen_for_client_messages(websocket: WebSocket,
                                     controller: Controller):
    logger.info("Starting listener for client messages...")
    while True:
        try:
            message = await websocket.receive_text()
            logger.trace(f"Message from client: '{message}'")

        except Exception as e:
            logger.error(f"Error while receiving message: {type(e).__name__} - {e}")
            break


@cam_ws_router.websocket("/ws/connect")
async def websocket_server_connect(websocket: WebSocket):
    await websocket.accept()
    logger.success(f"Websocket connection established!")

    await websocket.send_text("Hello, client!")

    async def websocket_send_bytes(data: bytes):
        await websocket.send_bytes(data)


    async with Controller(websocket_send_bytes) as controller:
        try:
            logger.important("Creating listener task...")
            listener_task = asyncio.create_task(listen_for_client_messages(websocket,
                                                                           controller))

            logger.important("Detecting cameras...")
            await controller.detect()

            logger.important("Starting camera group...")
            await controller.start_camera_group()


        except Exception as e:
            logger.exception(e)
            logger.error(f"Error while running camera loop: {type(e).__name__}- {e}")
        finally:
            logger.important("Websocket ended")
            listener_task.cancel()
            await websocket.close()
            logger.important("Websocket closed")
