import logging

from fastapi import APIRouter

from skellycam.api.app.app_state import get_app_state
from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)

detect_cameras_router = APIRouter()



@detect_cameras_router.get(
    "/detect",
    summary="Detect available cameras",
    description="Detect all available cameras connected to the system. "
                "This will return a list of cameras that the system can attempt to connect to, "
                "along with their available resolutions and framerates",
)
async def detect_cameras_route():
    logger.api("Received `detect/` request")
    get_app_state().add_api_call("cameras/detect")
    try:
        await get_controller().detect_available_cameras()
        logger.api(f"`detect/` request handled successfully")
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
