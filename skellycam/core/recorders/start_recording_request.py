from pydantic import BaseModel, Field


class StartRecordingRequest(BaseModel):
    recording_name: str = Field(default_factory=str, description="Name of the recording (NOTE: Doesn't do anything at the moment, filename is based on timestamp and determined by the recorder.)") #TODO - figure out a way to share the recording name with the recording manager from up top
    mic_device_index: int = Field(default=-1, description="Index of the microphone device to record audio from (0 for default, -1 for no audio recording)")
