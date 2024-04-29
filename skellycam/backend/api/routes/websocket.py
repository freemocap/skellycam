import logging
import traceback

from fastapi import APIRouter, WebSocket

from skellycam.backend.core.camera.config.camera_config import CameraConfigs
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()
@cam_ws_router.get("/start_camera_group")
async def start_camera_group(websocket: WebSocket, camera_configs:CameraConfigs):
    await websocket.accept()

    async def websocket_send(multi_frame_payload: MultiFramePayload):
        await websocket.send_bytes(multi_frame_payload.to_bytes())

    try:
        await get_controller().start_camera_group(websocket_send)
    except:
        logger.error("Websocket ended")
        traceback.print_exc()
        return

