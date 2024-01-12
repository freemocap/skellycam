from fastapi import APIRouter
from starlette.responses import RedirectResponse

from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras, CamerasDetectedResponse

router = APIRouter()
controller = get_or_create_controller()

router.get("/detect", response_model=CamerasDetectedResponse)(controller.detect_available_cameras)
