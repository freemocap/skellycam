import logging

from fastapi import APIRouter

from skellycam.api.models.base_models import BaseResponse
from skellycam.app.app_controller.app_controller import get_app_controller

logger = logging.getLogger(__name__)

close_cameras_router = APIRouter()


class CamerasClosedResponse(BaseResponse):
    pass


@close_cameras_router.get("/close",
                          summary="Close camera connections")
def close_camera_connections():
    logger.api("Received `/close` request...")

    try:
        get_app_controller().close_camera_group()
        logger.api("`/close` request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to close cameras: {type(e).__name__} - {e}")
        logger.exception(e)
