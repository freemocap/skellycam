import logging
import logging
import traceback

from fastapi import APIRouter, WebSocket

from skellycam.backend.core.controller import get_or_create_controller

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


@cam_ws_router.websocket("/ws/connect")
async def start_camera_group(websocket: WebSocket):
    await websocket.accept()
    logger.success(f"Websocket connection established!")
    controller = get_or_create_controller()
    try:
        await controller.start_camera_loop(websocket)
    except:
        logger.error("Websocket ended")
        traceback.print_exc()
    return
