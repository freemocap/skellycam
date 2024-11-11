import logging

from fastapi import APIRouter, Body

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller
from skellycam.core.recorders.start_recording_request import StartRecordingRequest

logger = logging.getLogger(__name__)

record_cameras_router = APIRouter()


@record_cameras_router.post("/record/start",
                           summary="Start recording video from cameras")
def start_recording(request: StartRecordingRequest = Body(..., examples=[StartRecordingRequest()])):
    logger.api("Received `/record/start` request...")
    get_skellycam_app_controller().start_recording(request)
    logger.api("`/record/start` request handled successfully.")


@record_cameras_router.get("/record/stop",
                           summary="Stop recording video from cameras")
def stop_recording():
    logger.api("Received `/record/stop` request...")
    get_skellycam_app_controller().stop_recording()
    logger.api("`/record/stop` request handled successfully.")
