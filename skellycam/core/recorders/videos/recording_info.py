import logging
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from skellycam.core.recorders.timestamps.full_timestamp import FullTimestamp

logger = logging.getLogger(__name__)
SYNCHRONIZED_VIDEOS_FOLDER_NAME = "synchronized_videos"
TIMESTAMPS_FOLDER_NAME = "synchronized_videos/timestamps"
CAMERA_TIMESTAMPS_FOLDER_NAME = "synchronized_videos/timestamps/camera_timestamps"


class RecordingInfo(BaseModel):
    recording_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recording_name: str
    recording_directory: str
    mic_device_index: int = -1

    recording_start_timestamp: FullTimestamp = Field(default_factory=FullTimestamp.now)

    @property
    def full_recording_path(self) -> str:
        rec_path = Path(f"{self.recording_directory}/{self.recording_name}")
        rec_path.mkdir(parents=True, exist_ok=True)
        return str(rec_path)

    @property
    def videos_folder(self) -> str:
        path = Path(self.full_recording_path)/SYNCHRONIZED_VIDEOS_FOLDER_NAME
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def timestamps_folder(self) -> str:
        path = Path(self.full_recording_path) / TIMESTAMPS_FOLDER_NAME
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def camera_timestamps_folder(self) -> str:
        path = Path(self.full_recording_path)/CAMERA_TIMESTAMPS_FOLDER_NAME
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def save_to_file(self):
        logger.debug(f"Saving recording info to [{self.full_recording_path}_info.json]")
        with open(str(Path(self.full_recording_path)/f"{self.recording_name}_info.json"), "w") as f:
            f.write(self.model_dump_json(indent=4))
