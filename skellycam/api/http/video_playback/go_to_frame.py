import logging

from fastapi import APIRouter, Body

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)
seek_videos_router = APIRouter()


@seek_videos_router.post("/seek_videos", summary="Open videos at folder path for playback")
def seek_videos(request: int = Body(..., examples=[400])): # TODO: make sure this is the right use of examples
    logger.api("Received `skellycam/video_playback/seek_videos` POST request...")
    try:
        get_skellycam_app_controller().seek_videos(frame_number=request)
        logger.api("`skellycam/video_playback/seek_videos` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/seek_videos` request: {type(e).__name__} - {e}")
        logger.exception(e)