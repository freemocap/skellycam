import logging
from pathlib import Path

from fastapi import APIRouter, Body

from skellycam.core.recorders.start_recording_request import StartRecordingRequest
from skellycam.skellycam_app.skellycam_app_state import get_skellycam_app_state

logger = logging.getLogger(__name__)

record_cameras_router = APIRouter(tags=["Recording"])


@record_cameras_router.post("/record/start",
                           summary="Start recording video from cameras")
def start_recording(request: StartRecordingRequest = Body(..., examples=[     StartRecordingRequest()])):
    logger.api("Received `/record/start` request...")
    if request.recording_path.startswith("~"):
        request.recording_path = request.recording_path.replace("~", str(Path.home()), 1)

    get_skellycam_app_state().start_recording(request)
    logger.api("`/record/start` request handled successfully.")


@record_cameras_router.get("/record/stop",
                           summary="Stop recording video from cameras")
def stop_recording():
    logger.api("Received `/record/stop` request...")
    get_skellycam_app_state().stop_recording()
    logger.api("`/record/stop` request handled successfully.")
