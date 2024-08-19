from pathlib import Path
from typing import Dict, Tuple

import cv2
from pydantic import BaseModel, ValidationError

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.frames.models.frame_metadata import FrameMetadata, FrameMetadaList, FRAME_METADATA_SHAPE
from skellycam.core.frames.models.frame_payload import FramePayload
from skellycam.core.frames.models.multi_frame_payload import MultiFramePayload
from skellycam.system.default_paths import create_recording_folder


class VideoFileSaver(BaseModel):
    camera_id: CameraId
    video_writer: cv2.VideoWriter

    @classmethod
    def create(cls,
               video_name: str,
               video_path: str,
               frame: FramePayload,
               config: CameraConfigs,
               ):
        cls._validate_input(frame=frame, config=config, video_path=video_path, video_name=video_name)
        writers = cls._initialize_video_writer(frame=frame,
                                               config=config,
                                               video_path=video_path)

    @classmethod
    def _initialize_video_writer(cls,
                                 frame: FramePayload,
                                 config: CameraConfig,
                                 video_path: str):
        recording_name = Path(video_path).parent.name
        file_format = config.video_file_format
        writer = cv2.VideoWriter(
            video_path + f"/{recording_name}_camera_{frame.camera_id}.{file_format}",  # filename
            cv2.VideoWriter_fourcc(*config.writer_fourcc),  # fourcc
            config.framerate,  # fps
            (frame.width, frame.height),  # frameSize
        )
        if not writer.isOpened():
            raise ValidationError(f"Failed to open video writer for camera {frame.camera_id}")


class FrameSaver(BaseModel):
    recording_name: str
    video_writers: Dict[CameraId, cv2.VideoWriter]
    frame_metadata_lists: Dict[CameraId, FrameMetadaList]

    @classmethod
    def create(cls,
               mf_payload: MultiFramePayload,
               camera_configs: CameraConfigs,
               recording_folder: str = create_recording_folder()):

        cls._validate_input(mf_payload=mf_payload, camera_configs=camera_configs, recording_folder=recording_folder)
        recording_name = Path(recording_folder).name
        videos_folder, metadata_folder = cls._create_subfolders(recording_folder)
        writers = {}
        metadata_lists = {}
        for camera_id, frame in mf_payload.frames.items():
            writers[camera_id] = VideoFileSaver.initialize(frame=frame,
                                                           config=camera_configs[camera_id],
                                                           recording_folder=recording_folder,
                                                           videos_folder=videos_folder)

            metadata_lists[camera_id] = FrameMetadaList.initialize(frame_metadata=FrameMetadata.create(frame=frame))

        return cls(recording_name=recording_name,
                   video_writers=writers,
                   frame_metadata_lists=metadata_lists)

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

        if not mf_payload.full:
            raise ValidationError(f"MultiFramePayload is not full")
        if not len(camera_configs) == len(mf_payload.frames):
            raise ValidationError(f"CameraConfigs and MultiFramePayload frames do not match")

        if not Path(recording_folder).exists():
            raise ValidationError(f"Recording folder path does not exist")

        for camera_id, frame in mf_payload.frames.items():
            if camera_id not in camera_configs:
                raise ValidationError(f"CameraConfig for camera {camera_id} is missing")
            cls._validate_frame(frame=frame, config=camera_configs[camera_id])

    @classmethod
    def _validate_frame(cls, frame: FramePayload, config: CameraConfig, video_path: str):
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
        if not Path(video_path).exists():
            raise ValidationError(f"Video path does not exist")
