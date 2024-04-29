import asyncio
import logging
import traceback

from fastapi import APIRouter, WebSocket

from skellycam.backend.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


@cam_ws_router.websocket("/ws/connect")
async def start_camera_group(websocket: WebSocket):
    await websocket.accept()
    logger.success(f"Websocket connection established!")
    await websocket.send_text(f"Connected!")
    await websocket.send_bytes(b"Connected!")

    async def websocket_send_multiframe(multi_frame_payload: MultiFramePayload):
        await websocket.send_bytes(multi_frame_payload.to_bytes())

    async def websocket_send_message(message: str):
        await websocket.send_text(message)

    try:
        with CameraGroupManager(websocket_send_multiframe, websocket_send_message) as manager:
            await manager.run()

    except:
        logger.error("Websocket ended")
        traceback.print_exc()
    return
