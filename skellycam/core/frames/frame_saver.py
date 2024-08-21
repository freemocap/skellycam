import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Tuple, Any

from pydantic import BaseModel, ValidationError

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.frames.metadata.frame_metadata import FrameMetadata, FRAME_METADATA_SHAPE
from skellycam.core.frames.metadata.frame_metadata_saver import FrameMetadataSaver
from skellycam.core.frames.payload_models.frame_payload import FramePayload
from skellycam.core.frames.payload_models.multi_frame_payload import MultiFramePayload
from skellycam.core.videos.video_saver import VideoSaver

logger = logging.getLogger(__name__)


class FrameSaver(BaseModel):
    recording_uuid: str = str(uuid.uuid4())
    recording_folder: str
    camera_configs: CameraConfigs

    video_savers: Dict[CameraId, VideoSaver]
    frame_metadata_savers: Dict[CameraId, FrameMetadataSaver]

    class Config:
        arbitrary_types_allowed = True

    @property
    def recording_info(self) -> "RecordingInfo":
        return RecordingInfo.from_frame_saver(self)

    @property
    def recording_name(self):
        return Path(self.recording_folder).name

    @classmethod
    def create(cls,
               mf_payload: MultiFramePayload,
               camera_configs: CameraConfigs,
               recording_folder: str):
        logger.trace(f"Creating FrameSaver for recording folder {recording_folder}")
        cls._validate_input(mf_payload=mf_payload, camera_configs=camera_configs, recording_folder=recording_folder)
        recording_name = Path(recording_folder).name
        videos_folder, metadata_folder = cls._create_subfolders(recording_folder)
        video_savers = {}
        metadata_lists = {}
        for camera_id, frame in mf_payload.frames.items():
            video_savers[camera_id] = VideoSaver.create(recording_name=recording_name,
                                                        videos_folder=videos_folder,
                                                        frame=frame,
                                                        config=camera_configs[camera_id],
                                                        )

            metadata_lists[camera_id] = FrameMetadataSaver.create(
                frame_metadata=FrameMetadata.from_array(metadata_array=frame.metadata),
                recording_name=recording_name,
                save_path=metadata_folder,
            )
        return cls(recording_folder=recording_folder,
                   camera_configs=camera_configs,
                   video_savers=video_savers,
                   frame_metadata_savers=metadata_lists)

    def add_multi_frame(self, mf_payload: MultiFramePayload):
        mf_payload.lifespan_timestamps_ns.append({"start_adding_multi_frame_to_framesaver": time.perf_counter_ns()})
        self._validate_multi_frame(mf_payload=mf_payload, camera_configs=self.camera_configs)
        mf_payload.lifespan_timestamps_ns.append({"before_add_multi_frame_to_video_savers": time.perf_counter_ns()})
        for camera_id, frame in mf_payload.frames.items():
            self._validate_frame(frame=frame, config=self.camera_configs[camera_id])
            self.video_savers[camera_id].add_frame(frame=frame)

        mf_payload.lifespan_timestamps_ns.append({"before_add_multi_frame_to_metadata_savers": time.perf_counter_ns()})
        for camera_id, frame in mf_payload.frames.items():
            self.frame_metadata_savers[camera_id].add_frame(frame=frame)
        mf_payload.lifespan_timestamps_ns.append({"done_adding_multi_frame_to_framesaver": time.perf_counter_ns()})
        logger.loop(f"Added multi-frame {mf_payload.multi_frame_number} to FrameSaver {self.recording_name}")

    @classmethod
    def _create_subfolders(cls, recording_folder: str) -> Tuple[str, str]:
        videos_folder = Path(recording_folder) / "videos"
        videos_folder.mkdir(parents=True, exist_ok=True)
        timestamps_folder = Path(videos_folder) / "timestamps"
        timestamps_folder.mkdir(parents=True, exist_ok=True)
        return str(videos_folder), str(timestamps_folder)

    @classmethod
    def _validate_input(cls,
                        mf_payload: MultiFramePayload,
                        camera_configs: CameraConfigs,
                        recording_folder: str):
        if not Path(recording_folder).exists():
            raise ValidationError(f"Recording folder path does not exist")

        cls._validate_multi_frame(mf_payload=mf_payload, camera_configs=camera_configs)

    @classmethod
    def _validate_multi_frame(cls, mf_payload: MultiFramePayload, camera_configs: CameraConfigs):
        if len(mf_payload.frames) == 0:
            raise ValidationError(f"MultiFramePayload is empty")
        if len(camera_configs) == 0:
            raise ValidationError(f"CameraConfigs is empty")
        if not mf_payload.full:
            raise ValidationError(f"MultiFramePayload is not full")
        if not len(camera_configs) == len(mf_payload.frames):
            raise ValidationError(f"CameraConfigs and MultiFramePayload frames do not match")

        for camera_id, frame in mf_payload.frames.items():
            if camera_id not in camera_configs:
                raise ValidationError(f"CameraConfig for camera {camera_id} is missing")
            cls._validate_frame(frame=frame, config=camera_configs[camera_id])

    @classmethod
    def _validate_frame(cls, frame: FramePayload, config: CameraConfig):
        if frame.camera_id != config.camera_id:
            raise ValidationError(
                f"Frame camera_id {frame.camera_id} does not match config camera_id {config.camera_id}")
        if frame.image.shape != (config.resolution.height, config.resolution.width, config.color_channels):
            raise ValidationError(f"Frame shape {frame.image.shape} does not match config shape "
                                  f"({config.resolution.height}, {config.resolution.width}, {config.color_channels})")
        if frame.metadata.shape != FRAME_METADATA_SHAPE:
            raise ValidationError(f"Metadata shape mismatch - "
                                  f"Expected: {FRAME_METADATA_SHAPE}, "
                                  f"Actual: {frame.metadata.shape}")

    def close(self):
        logger.debug("Closing FrameSaver...")
        for video_saver in self.video_savers.values():
            video_saver.close()
        for metadata_saver in self.frame_metadata_savers.values():
            metadata_saver.close()
        self.finalize_recording()

    def finalize_recording(self):
        logger.debug(f"Finalizing recording: `{self.recording_name}`...")
        self.finalize_timestamps()
        self.save_recording_summary()
        self.validate_recording()
        logger.success(f"Recording `{self.recording_name} Successfully recorded to: {self.recording_folder}")

    def finalize_timestamps(self):
        # TODO - combine all the `[camera]_timestamps.csv` into a combined `[recording]_timestamps.csv`
        pass

    def save_recording_summary(self):
        # TODO - save a summary of the recording to the recording folder, like stats and whatnot, also a `README.md`
        pass

    def validate_recording(self):
        # TODO - validate the recording, like check that there are the right numbers of videos and timestamps and whatnot
        pass


class RecordingInfo(BaseModel):
    recording_uuid: str = uuid.uuid4()
    recording_name: str
    recording_folder: str
    camera_configs: Dict[CameraId, Dict[str, Any]]  # CameraConfig model dump

    @classmethod
    def from_frame_saver(cls, frame_saver: FrameSaver):
        camera_configs = {camera_id: config.model_dump() for camera_id, config in frame_saver.camera_configs.items()}
        return cls(recording_name=frame_saver.recording_name,
                   recording_folder=frame_saver.recording_folder,
                   camera_configs=camera_configs)
