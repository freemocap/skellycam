import json
import logging
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.recorders.videos.parse_video_filename import ParsedVideoFilename
from skellycam.core.recorders.videos.video_associations import VideoAssociations
from skellycam.core.timestamps.full_timestamp import FullTimestamp
from skellycam.core.timestamps.recording_timing_reader import camera_timing_path
from skellycam.system.default_paths import get_default_recording_folder_path, CAMERA_TIMESTAMPS_FOLDER_NAME, \
    TIMESTAMPS_FOLDER_NAME, SYNCHRONIZED_VIDEOS_FOLDER_NAME
from skellycam.core.camera.config.image_rotation_types import rotation_int_to_name

logger = logging.getLogger(__name__)


class RecordingInfo(BaseModel):
    recording_name: str
    recording_directory: str  # Path to the directory where the recording will be saved, e.g., "~/skellycam_data/recordings"
    recording_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mic_device_index: int = -1

    recording_start_timestamp: FullTimestamp = Field(default_factory=FullTimestamp.now)

    @classmethod
    def create_temp(cls) -> 'RecordingInfo':
        """
        Create a temporary RecordingInfo object with a unique UUID and the specified recording name.
        """
        recording_path = get_default_recording_folder_path(tag="temp")
        return cls(
            recording_name=str(Path(recording_path).name),
            recording_directory=str(Path(recording_path).parent)
        )

    @property
    def full_recording_path(self) -> str:
        rec_path = Path(f"{self.recording_directory}/{self.recording_name}")
        rec_path.mkdir(parents=True, exist_ok=True)
        return str(rec_path)

    @property
    def videos_folder(self) -> str:
        path = Path(self.full_recording_path) / SYNCHRONIZED_VIDEOS_FOLDER_NAME
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def timestamps_folder(self) -> str:
        path = Path(self.full_recording_path) / TIMESTAMPS_FOLDER_NAME
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def timestamp_file_path(self) -> str:
        return f"{self.timestamps_folder}/{self.recording_name}_timestamps.csv"

    @property
    def camera_timestamps_folder(self) -> str:
        path = Path(self.full_recording_path) / CAMERA_TIMESTAMPS_FOLDER_NAME
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def recording_info_path(self) -> str:
        return str(Path(self.full_recording_path) / f"{self.recording_name}_info.json")

    @property
    def timestamp_stats_text_file_path(self) -> str:
        return f"{self.timestamps_folder}/{self.recording_name}_stats.txt"

    @property
    def timestamp_stats_json_file_path(self) -> str:
        return f"{self.timestamps_folder}/{self.recording_name}_stats.json"

    def save_to_file(self, camera_configs: CameraConfigs) -> None:
        logger.debug(f"Saving recording info to [{self.recording_info_path}]")
        recording_info_dict = self.model_dump()
        for camera_id, config in camera_configs.items():
            if camera_id != config.camera_id:
                raise ValueError(f"Camera configuration key {camera_id!r} disagrees with {config.camera_id!r}")
        associations = VideoAssociations({
            camera_id: Path(self.video_file_path_from_camera_config(config=config)).name
            for camera_id, config in camera_configs.items()
        })
        associations.resolve_paths(video_folder=Path(self.videos_folder))
        recording_info_dict["videos"] = associations.model_dump()
        recording_info_dict["camera_configs"] = {camera_id: config.model_dump() for camera_id, config in
                                                 camera_configs.items()}
        for camera_id, config in recording_info_dict["camera_configs"].items():
            recording_info_dict["camera_configs"][camera_id]["rotation"] = rotation_int_to_name(recording_info_dict["camera_configs"][camera_id]["rotation"])

        with open(self.recording_info_path, "w") as f:
            f.write(json.dumps(recording_info_dict, indent=4))

    def video_file_path_from_camera_config(self, config: CameraConfig, extension: str | None = None) -> str:
        ext = (extension or config.video_file_extension).lstrip(".")
        parsed = ParsedVideoFilename.from_camera_config(
            recording_name=self.recording_name,
            config=config,
            extension=ext,
        )
        videos_dir = Path(self.videos_folder)
        existing = sorted(path for path in videos_dir.glob(f"{parsed.stem}.*") if path.is_file())
        if len(existing) > 1:
            raise ValueError(f"Multiple videos match camera {config.camera_id!r}: {existing}")
        if existing:
            if extension and existing[0].suffix != f".{ext}":
                raise ValueError(f"Existing video {existing[0]} conflicts with requested extension {ext!r}")
            return str(existing[0])
        return str(videos_dir / parsed.filename)

    def camera_timestamps_file_path_from_camera_id(self, camera_id: str) -> str:
        path = camera_timing_path(recording_folder=Path(self.recording_directory) / self.recording_name, camera_id=camera_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def audio_file_path(self) -> str:
        return str(Path(self.videos_folder) / f"{self.recording_name}.audio.wav")

    @property
    def audio_timestamps_path(self) -> str:
        return str(Path(self.videos_folder) / f"{self.recording_name}.audio_timestamps.json")

    def __eq__(self, other):
        if not isinstance(other, RecordingInfo):
            return NotImplemented
        return self.model_dump_json() == other.model_dump_json()

    def __str__(self):
        return f"RecordingInfo(name={self.recording_name},\n directory={self.recording_directory},\n uuid={self.recording_uuid})"
