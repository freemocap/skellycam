import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)

play_videos_router = APIRouter()


@play_videos_router.get("/play_videos",
                          summary="Play video playback")
def close_camera_connections():
    logger.api("Received `/play_videos` request...")

    try:
        get_skellycam_app_controller().play_videos()
        logger.api("`/play_videos` request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to play videos: {type(e).__name__} - {e}")
        logger.exception(e)