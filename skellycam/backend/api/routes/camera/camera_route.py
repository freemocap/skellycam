import logging

from fastapi import APIRouter

from skellycam.backend.core.device_detection.detect_available_cameras import detect_available_cameras, \
    CamerasDetectedResponse

logger = logging.getLogger(__name__)

camera_router = APIRouter()

@camera_router.get(
    "/detect",
    response_model=CamerasDetectedResponse,
    summary="Detect available cameras",
)
def detect_available_cameras_route() -> CamerasDetectedResponse:
    """
    Detect all available cameras connected to the system.
    This will return a list of cameras that the system can attempt to connect to, along with
    their available resolutions and framerates
    """
    logger.info("Detecting available cameras...")
    try:
        return detect_available_cameras()
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        raise e
