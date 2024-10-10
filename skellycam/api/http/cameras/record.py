import logging

from fastapi import APIRouter

from skellycam.app.app_state import get_app_state
from skellycam.core.app_controller import get_app_controller

logger = logging.getLogger(__name__)

record_cameras_router = APIRouter()


@record_cameras_router.get("/record/start",
                           summary="Start recording video from cameras")
async def start_recording():
    logger.api("Received `/record/start` request...")
    get_app_state().start_recording()
    logger.api("`/record/start` request handled successfully.")


@record_cameras_router.get("/record/stop",
                           summary="Stop recording video from cameras")
async def stop_recording():
    logger.api("Received `/record/stop` request...")
    get_app_state().stop_recording()
    logger.api("`/record/stop` request handled successfully.")
