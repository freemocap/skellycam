import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_or_create_skellycam_app_controller

logger = logging.getLogger(__name__)

close_cameras_router = APIRouter()


@close_cameras_router.get("/close",
                          summary="Close camera connections")
def close_camera_connections():
    logger.api("Received `/close` request...")

    try:
        get_or_create_skellycam_app_controller().close_camera_group()
        logger.api("`/close` request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to close cameras: {type(e).__name__} - {e}")
        logger.exception(e)
