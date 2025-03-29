import logging
from pathlib import Path

from fastapi import APIRouter, Body

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.skellycam_app.skellycam_app import get_skellycam_app
from pydantic import BaseModel, Field

from skellycam.system.default_paths import get_default_recording_folder_path, default_recording_name

logger = logging.getLogger(__name__)

record_cameras_router = APIRouter(tags=["Recording"])


class StartRecordingRequest(BaseModel):
    recording_name: str = Field(default_factory=default_recording_name,
                                description="Name of the recording")
    recording_directory: str = Field(default_factory=get_default_recording_folder_path,
                                     description="Path to save the recording ")
    mic_device_index: int = Field(default=-1,
                                  description="Index of the microphone device to record audio from (0 for default, -1 for no audio recording)")

    def recording_full_path(self):
        return str(Path(self.recording_directory) / self.recording_name)

@record_cameras_router.post("/record/start",
                           summary="Start recording video from cameras")
def start_recording(request: StartRecordingRequest = Body(..., examples=[     StartRecordingRequest()])):
    logger.api("Received `/record/start` request...")
    if request.recording_directory.startswith("~"):
        request.recording_directory = str(Path(request.recording_directory.replace("~", str(Path.home()), 1)))
    Path(request.recording_directory).mkdir(parents=True, exist_ok=True)
    get_skellycam_app().start_recording(RecordingInfo(**request.model_dump()))
    logger.api("`/record/start` request handled successfully.")


@record_cameras_router.get("/record/stop",
                           summary="Stop recording video from cameras")
def stop_recording():
    logger.api("Received `/record/stop` request...")
    get_skellycam_app().stop_recording()
    logger.api("`/record/stop` request handled successfully.")
