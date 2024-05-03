import asyncio
import logging

from fastapi import APIRouter, WebSocket

from skellycam.backend.api.websocket import LATEST_FRAMES_REQUEST, CAMERA_READY_MESSAGE
from skellycam.backend.core.controller import Controller

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


async def listen_for_client_messages(websocket: WebSocket, controller: Controller):
    logger.info("Starting listener for client messages...")
    while True:
        try:
            message = await websocket.receive_text()
            logger.trace(f"Message from client: '{message}'")
            if message == LATEST_FRAMES_REQUEST:
                await controller.send_latest_frames()
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
            logger.important("Detecting cameras...")
            await controller.detect()

            logger.important("Starting camera group...")
            await controller.start_camera_group()

            logger.important("Waiting for cameras to be ready...")
            await controller.wait_for_cameras_ready()

            logger.important("Sending `cameras_ready` message to client...")
            await websocket.send_text(CAMERA_READY_MESSAGE)

            logger.important("Listening for client messages...")
            await listen_for_client_messages(websocket, controller)


        except Exception as e:
            logger.error(f"Error while running camera loop: {e}")
            logger.exception(e)
        finally:
            listener_task.cancel()
            logger.important("Websocket ended")
            await websocket.close()
            logger.important("Websocket closed")
