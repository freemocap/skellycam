import logging
from pathlib import Path

from fastapi import APIRouter, Body

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)
open_videos_router = APIRouter()


@open_videos_router.post("/open_videos", summary="Open videos at folder path for playback")
def open_videos(request: str | Path = Body(..., examples=["~/freemocap_data/recording_sessions/freemocap_test_data/synchronized_videos"])): # TODO: make sure this is the right use of examples
    logger.api("Received `skellycam/video_playback/open_videos` POST request...")
    try:
        get_skellycam_app_controller().open_video_group(video_folder_path=request)
        logger.api("`skellycam/video_playback/open_videos` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/open_videos` request: {type(e).__name__} - {e}")
        logger.exception(e)