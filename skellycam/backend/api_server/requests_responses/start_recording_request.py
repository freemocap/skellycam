from pydantic import BaseModel


class StartRecordingRequest(BaseModel):
    recording_folder_path: str
