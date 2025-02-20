import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)

pause_videos_router = APIRouter()


@pause_videos_router.get("/pause_videos",
                          summary="Pause video playback")
def close_camera_connections():
    logger.api("Received `/pause_videos` request...")

    try:
        get_skellycam_app_controller().pause_videos()
        logger.api("`/pause_videos` request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to pause videos: {type(e).__name__} - {e}")
        logger.exception(e)