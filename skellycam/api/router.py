from fastapi import APIRouter

from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)
from skellycam.backend.controller.interactions.connect_to_cameras import (
    CamerasConnectedResponse,
    ConnectToCamerasRequest,
)
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload

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


@router.get("/cameras", response_model=CameraConfigs)
def get_cameras() -> CameraConfigs:
    return controller.camera_group_manager.camera_configs


@router.get("/cameras/latest_frontend_payload", response_model=MultiFramePayload)
def get_latest_frames() -> MultiFramePayload:
    return controller.camera_group_manager.get_latest_frontend_payload()
