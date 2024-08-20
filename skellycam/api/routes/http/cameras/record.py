import logging

from fastapi import APIRouter

from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)

record_cameras_router = APIRouter()


@record_cameras_router.get("record/start",
                           summary="Start recording video from cameras")
async def start_recording(recording_name_tag: str):
    logger.api("Received `/record/start` request...")
    get_controller().start_recording()
    logger.api("`/record/start` request handled successfully.")


@record_cameras_router.get("record/stop",
                           summary="Stop recording video from cameras")
async def start_recording(recording_name_tag: str):
    logger.api("Received `/record/stop` request...")
    get_controller().stop_recording()
    logger.api("`/record/stop` request handled successfully.")
