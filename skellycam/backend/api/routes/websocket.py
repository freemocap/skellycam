import logging
import traceback

from fastapi import APIRouter, WebSocket

from skellycam.backend.core.camera.config.camera_config import CameraConfigs
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()
@cam_ws_router.websocket("/ws/connect}")
async def start_camera_group(websocket: WebSocket, webcam_id: str):
    logger.info(f"Received websocket `connect` request for camera group on webcam {webcam_id}")
    await websocket.accept()
    logger.success(f"Websocket connection established for camera group on webcam {webcam_id}!")
    async def websocket_send(multi_frame_payload: MultiFramePayload):
        await websocket.send_bytes(multi_frame_payload.to_bytes())

    try:
        await websocket.send_text(f"Connected! - {webcam_id}")
        await websocket.send_bytes(b"Connected! - {webcam_id}")
    except:
        logger.error("Websocket ended")
        traceback.print_exc()
        return

