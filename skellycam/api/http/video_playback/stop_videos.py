import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)

stop_videos_router = APIRouter()


@stop_videos_router.get("/stop_videos",
                          summary="Stop video playback")
def close_camera_connections():
    logger.api("Received `/stop_videos` request...")

    try:
        get_skellycam_app_controller().stop_videos()
        logger.api("`/stop_videos` request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to stop videos: {type(e).__name__} - {e}")
        logger.exception(e)