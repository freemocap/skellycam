import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)

close_videos_router = APIRouter()


@close_videos_router.get("/close_videos",
                          summary="Close video connections")
def close_camera_connections():
    logger.api("Received `/close_videos` request...")

    try:
        get_skellycam_app_controller().close_video_group()
        logger.api("`/close_videos` request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to close videos: {type(e).__name__} - {e}")
        logger.exception(e)