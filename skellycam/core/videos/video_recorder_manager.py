import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Any

from pydantic import BaseModel, ValidationError, Field

from skellycam.core import CameraId
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.timestamps.full_timestamp import FullTimestamp
from skellycam.core.timestamps.multiframe_timestamp_logger import MultiframeTimestampLogger
from skellycam.core.videos.video_recorder import VideoRecorder

# TODO - Create a 'recording folder schema' of some kind specifying the structure of the recording folder
SYNCHRONIZED_VIDEOS_FOLDER_NAME = "synchronized_videos"
TIMESTAMPS_FOLDER_NAME = "synchronized_videos"

SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME = f"{SYNCHRONIZED_VIDEOS_FOLDER_NAME}_README.md"

# TODO - Flesh out the README content
SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT = f"""# Synchronized Videos Folder
This folder contains the synchronized videos and timestamps for a recording session.

Each video in this folder should have precisely the same number of frames, each of which corresponds to the same time period across all cameras (i.e. 'frame 12 in camera 1' should represent an image of the same moment in time as 'frame 12 in camera 2' etc.) 
"""

logger = logging.getLogger(__name__)


class VideoRecorderManager(BaseModel):
    recording_uuid: str = str(uuid.uuid4())
    recording_folder: str
    recording_name: str
    camera_configs: CameraConfigs

    video_recorders: Dict[CameraId, VideoRecorder]
    multi_frame_timestamp_logger: MultiframeTimestampLogger

    class Config:
        arbitrary_types_allowed = True

    @property
    def recording_info(self) -> "RecordingInfo":
        return RecordingInfo.from_video_recorder_manager(self)

    @classmethod
    def create(cls,
               first_multi_frame_payload: MultiFramePayload,
               camera_configs: CameraConfigs,
               recording_folder: str):
        """
        NOTE - Does not add `first mf payload` to videos - call `add mf payload` after creation
        """

        logger.debug(f"Creating FrameSaver for recording folder {recording_folder}")
        cls._validate_input(mf_payload=first_multi_frame_payload,
                            camera_configs=camera_configs,
                            recording_folder=recording_folder)
        recording_name = Path(recording_folder).name
        videos_folder = cls._create_videos_folder(recording_folder)
        video_recorders = {}
        for camera_id, frame in first_multi_frame_payload.frames.items():
            video_recorders[camera_id] = VideoRecorder.create(recording_name=recording_name,
                                                              videos_folder=videos_folder,
                                                              frame=frame,
                                                              config=camera_configs[camera_id],
                                                              )

        return cls(recording_folder=recording_folder,
                   recording_name=recording_name,
                   camera_configs=camera_configs,
                   video_recorders=video_recorders,
                   multi_frame_timestamp_logger=MultiframeTimestampLogger.from_first_multiframe(
                       first_multiframe=first_multi_frame_payload,
                       video_save_directory=videos_folder,
                       recording_name=recording_name,
                   ))

    def add_multi_frame(self, mf_payload: MultiFramePayload):
        logger.loop(f"Adding multi-frame {mf_payload.multi_frame_number} to video recorder for:  {self.recording_name}")

        mf_payload.lifespan_timestamps_ns.append({"start_adding_multi_frame_to_video_recorder": time.perf_counter_ns()})
        self._validate_multi_frame(mf_payload=mf_payload, camera_configs=self.camera_configs)
        mf_payload.lifespan_timestamps_ns.append({"before_add_multi_frame_to_video_savers": time.perf_counter_ns()})
        for camera_id, frame in mf_payload.frames.items():
            self._validate_frame(frame=frame, config=self.camera_configs[camera_id])
            self.video_recorders[camera_id].add_frame(frame=frame)

        mf_payload.lifespan_timestamps_ns.append({"before_logging_multi_frame": time.perf_counter_ns()})
        self.multi_frame_timestamp_logger.log_multiframe(multi_frame_payload=mf_payload)


    @classmethod
    def _create_videos_folder(cls, recording_folder: str) -> str:
        videos_folder = Path(recording_folder) / SYNCHRONIZED_VIDEOS_FOLDER_NAME
        videos_folder.mkdir(parents=True, exist_ok=True)
        cls._save_folder_readme(videos_folder)
        return str(videos_folder)

    @classmethod
    def _save_folder_readme(cls, videos_folder):
        # save the readme
        with open(f"{videos_folder}/{SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME}", "w") as f:
            f.write(SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT)

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
        if not camera_configs.keys() == mf_payload.frames.keys():
            raise ValidationError(f"CameraConfigs and MultiFramePayload frames do not match")

    @classmethod
    def _validate_frame(cls, frame: FramePayload, config: CameraConfig):
        if frame.camera_id != config.camera_id:
            raise ValidationError(
                f"Frame camera_id {frame.camera_id} does not match config camera_id {config.camera_id}")
        if frame.image.shape != (config.resolution.height, config.resolution.width, config.color_channels):
            raise ValidationError(f"Frame shape {frame.image.shape} does not match config shape "
                                  f"({config.resolution.height}, {config.resolution.width}, {config.color_channels})")


    def close(self):
        logger.debug(f"Closing {self.__class__.__name__} for recording: `{self.recording_name}`")
        for video_saver in self.video_recorders.values():
            video_saver.close()
        self.multi_frame_timestamp_logger.close()
        self.finalize_recording()

    def finalize_recording(self):
        logger.debug(f"Finalizing recording: `{self.recording_name}`...")
        self.finalize_timestamps()
        self.save_recording_summary()
        self.validate_recording()
        logger.success(f"Recording `{self.recording_name} Successfully recorded to: {self.recording_folder}")

    def finalize_timestamps(self):
        # TODO - add clean up and optional tasks... calc stats, save to individual cam timestamp files, etc
        pass

    def save_recording_summary(self):
        # TODO - Update the `recording_info` with the final recording info? Or maybe a separeate `RecordingStats` save?
        # Save the recording info to a `[recording_name]_info.json` in the recording folder
        self.recording_info.save_to_file()

    def validate_recording(self):
        # TODO - validate the recording, like check that there are the right numbers of videos and timestamps and whatnot
        pass


class RecordingInfo(BaseModel):
    recording_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recording_name: str
    recording_folder: str
    camera_configs: Dict[CameraId, Dict[str, Any]]  # CameraConfig model dump

    recording_start_timestamp: FullTimestamp = Field(default_factory=FullTimestamp.now)

    @classmethod
    def from_video_recorder_manager(cls, frame_saver: VideoRecorderManager):
        camera_configs = {camera_id: config.model_dump() for camera_id, config in frame_saver.camera_configs.items()}
        return cls(recording_name=frame_saver.recording_name,
                   recording_folder=frame_saver.recording_folder,
                   camera_configs=camera_configs)

    def save_to_file(self):
        logger.debug(f"Saving recording info to [{self.recording_folder}/{self.recording_name}_info.json]")
        with open(f"{self.recording_folder}/{self.recording_name}_info.json", "w") as f:
            f.write(self.model_dump_json(indent=4))
