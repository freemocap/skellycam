from pathlib import Path

from pydantic import BaseModel


class StartRecordingRequest(BaseModel):
    save_folder: str

    @property
    def save_folder_path(self):
        path = Path(self.save_folder)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def save_folder_str(self):
        return str(self.save_folder_path)

    @property
    def recording_name(self):
        return self.save_folder_path.name
