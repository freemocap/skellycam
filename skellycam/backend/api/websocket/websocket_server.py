import logging

from fastapi import APIRouter, WebSocket

from skellycam.backend.core.controller.controller import Controller
from skellycam.backend.core.controller.singleton import set_controller

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


async def listen_for_client_messages(websocket: WebSocket):
    logger.info("Starting listener for client messages...")
    while True:
        try:
            message = await websocket.receive_text()
            logger.debug(f"Message from client: '{message}'")

            if not message:
                logger.important("Empty message received, ending listener task...")
                break

        except Exception as e:
            logger.error(f"Error while receiving message: {type(e).__name__} - {e}")
            break


@websocket_router.websocket("/ws/connect")
async def websocket_server_connect(websocket: WebSocket):
    await websocket.accept()
    logger.success(f"Websocket connection established!")

    await websocket.send_text("Hello, client!")

    async def websocket_send_bytes(data: bytes):
        await websocket.send_bytes(data)


    async with Controller(websocket_send_bytes) as controller:
        set_controller(controller)
        try:
            logger.important("Creating listener task...")
            await listen_for_client_messages(websocket)

            # logger.important("Detecting cameras...")
            # await controller.detect()
            #
            # logger.important("Starting camera group...")
            # await controller.start_camera_group()


        except Exception as e:
            logger.exception(e)
            logger.error(f"Error while running camera loop: {type(e).__name__}- {e}")
        finally:
            logger.important("Websocket ended")
            await websocket.close()
            logger.important("Websocket closed")
