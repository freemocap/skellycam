import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)

detect_cameras_router = APIRouter()


@detect_cameras_router.get(
    "/detect",
    summary="Detect available cameras",
    description="Detect all available cameras connected to the system. "
                "This will return a list of cameras that the system can attempt to connect to, "
                "along with their available resolutions and framerates",
)
def detect_cameras_route():
    # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client
    logger.api("Received `detect/` request")
    try:
        get_skellycam_app_controller().detect_available_cameras()
        logger.api(f"`detect/` request handled successfully")
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
