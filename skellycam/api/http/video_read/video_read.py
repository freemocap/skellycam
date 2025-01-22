import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)
video_read_router = APIRouter()


@video_read_router.get("/video_read", summary="Read videos as multi frame payloads")
def read_videos():
    """

    """
    logger.api("")

    # TODO: fill this in based on connect_to_cameras functionality

    return ...