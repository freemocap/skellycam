import logging

from fastapi import APIRouter

from skellycam.backend.api.models.base_models import BaseResponse
from skellycam.backend.core.controller.singleton import get_controller
from skellycam.backend.core.device_detection.detect_available_cameras import DetectedCameras

logger = logging.getLogger(__name__)

detect_cameras_router = APIRouter()


class CamerasDetectedResponse(BaseResponse):
    detected_cameras: DetectedCameras


@detect_cameras_router.get(
    "/detect",
    response_model=CamerasDetectedResponse,
    summary="Detect available cameras",
    description="Detect all available cameras connected to the system. "
                "This will return a list of cameras that the system can attempt to connect to, "
                "along with their available resolutions and framerates",
)
async def detect_cameras_route() -> CamerasDetectedResponse:
    controller = get_controller()
    logger.info("Detecting available cameras...")
    try:
        detected_cameras  = await controller.detect()
        return CamerasDetectedResponse(detected_cameras=detected_cameras)
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        return CamerasDetectedResponse.from_exception(e)

# @camera_router.get("/close",
#                    summary="Close camera connections")
# async def close_camera_connections():
#     global controller
#     if not controller.connected:
#         return {"message": "No camera connections to close"}
#     logger.info("Closing camera connections...")
#     await controller.close()
#     return {"message": "Camera connections closed"}
