from pathlib import Path

from pydantic import BaseModel, Field

from skellycam.system.default_paths import get_default_recording_folder_path


class StartRecordingRequest(BaseModel):
    recording_name: str = Field(default_factory=str, description="Name of the recording ")
    recording_path: str = Field(default_factory=get_default_recording_folder_path, description="Path to save the recording ")
    mic_device_index: int = Field(default=-1, description="Index of the microphone device to record audio from (0 for default, -1 for no audio recording)")
