import logging
import time
from pathlib import Path
from typing import Dict, Tuple

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
    recording_name: str
    camera_configs: CameraConfigs

    video_savers: Dict[CameraId, VideoSaver]
    frame_metadata_savers: Dict[CameraId, FrameMetadataSaver]

    @classmethod
    def create(cls,
               mf_payload: MultiFramePayload,
               camera_configs: CameraConfigs,
               recording_folder: str):
        logger.debug(f"Creating FrameSaver for recording folder {recording_folder}")
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

            metadata_lists[camera_id] = FrameMetadataSaver.create(frame_metadata=FrameMetadata.create(frame=frame))
        return cls(recording_name=recording_name,
                   camera_configs=camera_configs,
                   video_writers=video_savers,
                   frame_metadata_lists=metadata_lists)

    def add_multi_frame(self, mf_payload: MultiFramePayload):
        mf_payload.lifecycle_timestamps_ns.append({"start_adding_multi_frame_to_framesaver": time.perf_counter_ns()})
        self._validate_multi_frame(mf_payload=mf_payload, camera_configs=self.camera_configs)
        mf_payload.lifecycle_timestamps_ns.append({"before_add_multi_frame_to_video_savers": time.perf_counter_ns()})
        for camera_id, frame in mf_payload.frames.items():
            self._validate_frame(frame=frame, config=self.camera_configs[camera_id])
            self.video_savers[camera_id].add_frame(frame=frame)

        mf_payload.lifecycle_timestamps_ns.append({"before_add_multi_frame_to_metadata_savers": time.perf_counter_ns()})
        for camera_id, frame in mf_payload.frames.items():
            self.frame_metadata_lists[camera_id].add_frame(FrameMetadata.create(frame=frame))
        mf_payload.lifecycle_timestamps_ns.append({"done_adding_multi_frame_to_framesaver": time.perf_counter_ns()})

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
        if len(mf_payload.frames) == 0 or len(camera_configs) == 0:
            raise ValidationError(f"MultiFramePayload or CameraConfigs are empty")

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
        if frame.image.shape != (config.height, config.width, config.color_channels):
            raise ValidationError(f"Frame shape {frame.image.shape} does not match config shape "
                                  f"({config.height}, {config.width}, {config.color_channels})")
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

        self.finalize_timestamps()
        self.save_recording_summary()

    def f