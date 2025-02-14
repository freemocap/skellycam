import logging
import uuid
from typing import TYPE_CHECKING, Any, Dict

from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.recorders.timestamps.full_timestamp import FullTimestamp

if TYPE_CHECKING:
    from skellycam.core.recorders.recording_manager import RecordingManager

logger = logging.getLogger(__name__)


class RecordingInfo(BaseModel):
    type: str = "RecordingInfo"
    recording_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recording_name: str
    recording_folder: str
    camera_configs: Dict[CameraId, Dict[str, Any]]  # CameraConfig model dump

    recording_start_timestamp: FullTimestamp = Field(default_factory=FullTimestamp.now)

    @classmethod
    def from_recording_manager(cls, frame_saver: 'RecordingManager'):
        camera_configs = {camera_id: config.model_dump() for camera_id, config in frame_saver.camera_configs.items()}
        return cls(recording_name=frame_saver.recording_name,
                   recording_folder=frame_saver.recording_folder,
                   camera_configs=camera_configs)

    def save_to_file(self):
        logger.debug(f"Saving recording info to [{self.recording_folder}/{self.recording_name}_info.json]")
        with open(f"{self.recording_folder}/{self.recording_name}_info.json", "w") as f:
            f.write(self.model_dump_json(indent=4))
