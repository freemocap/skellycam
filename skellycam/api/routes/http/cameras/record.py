import logging

from fastapi import APIRouter

from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)

record_cameras_router = APIRouter()


@record_cameras_router.get("/record/start",
                           summary="Start recording video from cameras")
async def start_recording(recording_name_tag: str) -> bool:
    logger.api("Received `/record/start` request...")
    success = get_controller().start_recording()
    logger.api("`/record/start` request handled successfully.")
    return success


@record_cameras_router.get("/record/stop",
                           summary="Stop recording video from cameras")
async def start_recording(recording_name_tag: str) -> bool:
    logger.api("Received `/record/stop` request...")
    success = get_controller().stop_recording()
    logger.api("`/record/stop` request handled successfully.")
    return success
