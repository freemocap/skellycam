import asyncio
import logging

from fastapi import APIRouter, WebSocket

from skellycam.backend.api.websocket import LATEST_FRAMES_REQUEST
from skellycam.backend.core.controller import Controller

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


async def listen_for_client_messages(websocket: WebSocket, controller: Controller):
    while True:
        try:
            message = await websocket.receive_text()
            logger.info(f"Message from client: '{message}'")
            if message == LATEST_FRAMES_REQUEST:
                await controller.send_latest_frames()
        except Exception as e:
            logger.error(f"Error while receiving message: {type(e).__name__} - {e}")
            break


@cam_ws_router.websocket("/ws/connect")
async def start_camera_group(websocket: WebSocket):
    await websocket.accept()
    logger.success(f"Websocket connection established!")

    await websocket.send_text("Hello, client!")

    async def websocket_send_bytes(data: bytes):
        await websocket.send_bytes(data)

    async with Controller(websocket_send_bytes) as controller:
        try:
            listener_task = asyncio.create_task(listen_for_client_messages(websocket, controller))
            await controller.detect()
            camera_loop = controller.start_camera_group()
            await camera_loop

        except Exception as e:
            logger.error(f"Error while running camera loop: {e}")
            logger.exception(e)
        finally:
            listener_task.cancel()
            logger.info("Websocket ended")
            await websocket.close()
            logger.info("Websocket closed")
