from fastapi import APIRouter
from starlette.websockets import WebSocket

from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)
from skellycam.backend.controller.interactions.connect_to_cameras import (
    CamerasConnectedResponse,
    ConnectToCamerasRequest,
)

router = APIRouter()
controller = get_or_create_controller()


@router.get("/hello")
async def hello():
    return {"message": "Hello from the SkellyCam API 💀📸✨"}


@router.get("/detect", response_model=CamerasDetectedResponse)
def detect_available_cameras() -> CamerasDetectedResponse:
    return controller.detect_available_cameras()


@router.post("/connect", response_model=CamerasConnectedResponse)
def connect_to_cameras(request: ConnectToCamerasRequest):
    return controller.connect_to_cameras(request.camera_configs)


@router.websocket("/websocket")
async def websocket(websocket: WebSocket):
    await websocket.accept()
    while True:
        if controller.camera_group_manager.new_multiframe_available():
            latest_multiframe = await controller.new_multiframe()
            await websocket.send_bytes(len(latest_multiframe.to_bytes()))
        else:
            await asyncio.sleep(0.01)
