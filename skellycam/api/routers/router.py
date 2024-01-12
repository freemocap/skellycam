from fastapi import APIRouter

from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras, CamerasDetectedResponse

router = APIRouter()

router.get("/cameras", response_model=CamerasDetectedResponse)(detect_available_cameras)
