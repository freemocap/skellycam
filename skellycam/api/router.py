from fastapi import APIRouter

from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    CamerasDetectedResponse
from skellycam.backend.controller.interactions.connect_to_cameras import ConnectToCamerasResponse, \
    ConnectToCamerasRequest

router = APIRouter()
controller = get_or_create_controller()

router.get("/detect", response_model=CamerasDetectedResponse)(controller.detect_available_cameras)


camera_router = APIRouter()
@camera_router.post("/connect", response_model=ConnectToCamerasResponse)
def connect_to_cameras(request: ConnectToCamerasRequest):
    return controller.connect_to_cameras(request.camera_configs)

# Include the camera_router in the main router
router.include_router(camera_router, prefix="/camera")