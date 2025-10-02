import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from skellycam.skellycam_app.skellycam_app import get_skellycam_app

logger = logging.getLogger(__name__)
load_videos_router = APIRouter()
DEFAULT_VIDEOS_PATH = Path().home() / "freemocap_data" / "recording_sessions" / "freemocap_test_data" / "synchronized_videos"

def get_test_videos() -> list[str]:
    # case insensitive glob all video files in the directory
    video_paths = []
    for ext in ['*.mp4', '*.avi', '*.mov']:
        for video_path in DEFAULT_VIDEOS_PATH.glob(ext):
            video_paths.append(str(video_path))
    return video_paths

class LoadRecordingRequest(BaseModel):
    video_paths: list[str] = Field(default_factory=get_test_videos, description="List of paths to synchronized videos that all have exactly the same number of frames")

class LoadRecordingResponse(BaseModel):
    frame_count: int = Field(default=0, ge=0, description="Total number of frames across all videos in the recording session.")


@load_videos_router.post("/load_videos", response_model=LoadRecordingResponse, tags=["Videos"])
async def load_recording_endpoint(request: LoadRecordingRequest = Body(..., description="Request body containing the path to the recording directory",
                                                                       examples=[LoadRecordingRequest()])
                                  ) -> LoadRecordingResponse:
    logger.info(f"Loading recording from path: {request.recording_path}")
    if not Path(request.recording_path).is_dir():
        error_msg = f"Recording path does not exist or is not a directory: {request.recording_path}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    try:
        get_skellycam_app().set_recording_path(str(request.recording_path))
        return LoadRecordingResponse.from_app_state(get_skellyclicker_app_state())
    except ValueError as e:
        error_msg = f"Invalid recording path: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Failed to load recording: {type(e).__name__} - {str(e)}"
        logger.exception(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
