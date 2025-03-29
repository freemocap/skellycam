import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.recorders.timestamps.full_timestamp import FullTimestamp

if TYPE_CHECKING:
    from skellycam.core.recorders.recording_manager import RecordingManager

logger = logging.getLogger(__name__)


class RecordingInfo(BaseModel):
    recording_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recording_name: str
    recording_directory: str
    mic_device_index: int = -1

    recording_start_timestamp: FullTimestamp = Field(default_factory=FullTimestamp.now)

    @property
    def recording_path(self) -> str:
        return str(Path(f"{self.recording_directory}/{self.recording_name}"))

    @classmethod
    def from_recording_manager(cls, recording_manager: 'RecordingManager'):
        return cls(recording_name=recording_manager.recording_name,
                   recording_directory=recording_manager.recording_folder
                     )

    def save_to_file(self):
        logger.debug(f"Saving recording info to [{self.recording_directory}/{self.recording_name}_info.json]")
        with open(f"{self.recording_directory}/{self.recording_name}_info.json", "w") as f:
            f.write(self.model_dump_json(indent=4))
