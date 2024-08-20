import logging
from typing import Optional

from fastapi import APIRouter

from skellycam.api.models.base_models import BaseResponse
from skellycam.core.controller import Controller, get_controller
from skellycam.core.detection.detect_available_devices import AvailableDevices

logger = logging.getLogger(__name__)

detect_cameras_router = APIRouter()


class DetectCamerasResponse(BaseResponse):
    detected_cameras: Optional[AvailableDevices]


@detect_cameras_router.get(
    "/detect",
    response_model=DetectCamerasResponse,
    summary="Detect available cameras",
    description="Detect all available cameras connected to the system. "
                "This will return a list of cameras that the system can attempt to connect to, "
                "along with their available resolutions and framerates",
)
async def detect_cameras_route() -> DetectCamerasResponse:
    controller: Controller = get_controller()

    logger.api("Received `detect/` request")
    try:
        detected_cameras = await controller.detect()
        logger.api(f"`detect/` request handled successfully - detected cameras: [{detected_cameras}]")
        return DetectCamerasResponse(detected_cameras=detected_cameras)
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        return DetectCamerasResponse.from_exception(e)
