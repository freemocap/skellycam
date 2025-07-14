import logging
import threading
import uuid
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.timestamps.recording_timestamps import RecordingTimestamps
from skellycam.core.recorders.videos.recording_info import RecordingInfo, SYNCHRONIZED_VIDEOS_FOLDER_NAME
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.types.type_overloads import CameraIdString, RecordingManagerIdString

# TODO - Create a 'recording folder schema' of some kind specifying the structure of the recording folder


SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME = f"{SYNCHRONIZED_VIDEOS_FOLDER_NAME}_README.md"

# TODO - Flesh out the README content
SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT = f"""# Synchronized Videos Folder
This folder contains the synchronized videos and timestamps for a recording session.

Each video in this folder should have precisely the same number of frames, each of which corresponds to the same time period across all cameras (i.e. 'frame 12 in camera 1' should represent an image of the same moment in time as 'frame 12 in camera 2' etc.) 
"""

logger = logging.getLogger(__name__)


class RecordingManager(BaseModel):
    recording_info: RecordingInfo
    camera_configs: CameraConfigs
    recording_timestamps: RecordingTimestamps
    is_finished: bool = False

    model_config = ConfigDict(arbitrary_types_allowed = True)

    @classmethod
    def create(cls,
               recording_info: RecordingInfo,
               camera_configs: CameraConfigs,
               ):

        logger.debug(f"Creating RecordingManager for recording folder {recording_info.recording_name}")

        return cls(recording_info=recording_info,
                     camera_configs=camera_configs,
                   recording_timestamps=RecordingTimestamps(recording_info=recording_info),
                   )

    @property
    def anything_recorded(self) -> bool:
        return self.recording_timestamps.anything_recorded

    def add_mf_timestamps(self,  mf_timestamps: dict[CameraIdString, np.recarray]):
        """
        Adds multi-frame timestamps to the recording manager.
        This is used to synchronize frames across multiple cameras.
        """
        self.recording_timestamps.add_mf_timestamps(mf_timestamps)

    def finalize_recording(self):
        logger.debug(f"Finalizing recording: `{self.recording_info.recording_name}`...")
        self.recording_info.save_to_file()
        self.validate_recording()
        self.recording_timestamps.save_timestamps()
        self._save_folder_readme()
        self.is_finished = True
        logger.success(
            f"Recording `{self.recording_info.recording_name} Successfully recorded to: {self.recording_info.recording_directory}")
    def _save_folder_readme(self):
        with open(str(Path(self.recording_info.videos_folder) / SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME), "w") as f:
            f.write(SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT)

    def validate_recording(self):
        """
        Validates the recording by checking:
        1. All videos were saved and exist on disk
        2. All videos have the same number of frames
        3. Timestamps were saved and exist on disk
        4. Timestamps have the same number of frames as the videos

        Raises a ValueError if any validation check fails.
        """
        logger.debug(f"Validating recording: {self.recording_info.recording_name}")

        video_paths: dict[CameraIdString, Path] = {}
        # Check 1: Verify all video files exist
        for camera_config in self.camera_configs.values():
            video_path = Path(self.recording_info.video_file_path_from_camera_config(camera_config))
            if video_path.exists() and video_path.is_file():
                logger.trace(f"Recording Validation Check#1 - Found video file for camera {camera_config.camera_id}: {video_path}")
            video_paths[camera_config.camera_id] = video_path

        #Verify all videos are expected shape and have the same number of frames
        frame_counts = {}
        for camera_id, video_path in video_paths.items():
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"Failed to open video file for camera {camera_id}: {video_path}")

            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_counts[camera_id] = frame_count
            success, frame = cap.read()
            if not success:
                raise ValueError(f"Failed to read first frame from video file for camera {camera_id}: {video_path}")
            if frame is None or frame.size == 0:
                raise ValueError(f"Video file for camera {camera_id} is empty or corrupted: {video_path}")
            if frame.shape != self.camera_configs[camera_id].image_shape:
                raise ValueError(f"Video file for camera {camera_id} has unexpected shape: {frame.shape}. "
                                 f"Expected: {self.camera_configs[camera_id].image_shape}")
            cap.release()

            logger.trace(f"Recording Validation Check#2 - Camera {camera_id} video has {frame_count} frames")

        if len(set(frame_counts.values())) > 1:
            frame_count_str = ", ".join([f"{camera_id}: {count}" for camera_id, count in frame_counts.items()])
            raise ValueError(f"Videos have different frame counts: {frame_count_str}")

        expected_frame_count = next(iter(frame_counts.values())) if frame_counts else 0
        logger.trace(f"Recording Validation Check#2 - All videos have {expected_frame_count} frames")

        # Check 3: Verify timestamp files exist
        timestamp_file = Path(
            f"{self.recording_info.timestamps_folder}/{self.recording_info.recording_name}_timestamps.csv")
        if not timestamp_file.exists() and len(self.video_recorders) > 1:
            raise ValueError(f"Multiframe timestamp file does not exist: {timestamp_file}")

        camera_timestamp_files = {}
        for camera_id in self.video_recorders.keys():
            camera_ts_file = Path(
                f"{self.recording_info.camera_timestamps_folder}/{self.recording_info.recording_name}_camera_{camera_id}_timestamps.csv")
            if not camera_ts_file.exists():
                raise ValueError(f"Camera timestamp file for camera {camera_id} does not exist: {camera_ts_file}")
            camera_timestamp_files[camera_id] = camera_ts_file
            logger.trace(
                f"Recording Validation Check#3 - Camera timestamp file for camera {camera_id} exists: {camera_ts_file}")

        # Check 4: Verify timestamps have the same number of frames as videos
        for camera_id, ts_file in camera_timestamp_files.items():
            try:
                import pandas as pd
                df = pd.read_csv(ts_file)
                ts_frame_count = len(df)

                if ts_frame_count != frame_counts[camera_id]:
                    raise ValueError(
                        f"Camera {camera_id} has {frame_counts[camera_id]} video frames but {ts_frame_count} timestamp entries")

                logger.trace(
                    f"Recording Validation Check#4 - Camera {camera_id} has matching frame count in video and timestamps: {ts_frame_count}")
            except Exception as e:
                raise ValueError(f"Error validating timestamp file for camera {camera_id}: {e}")

        # If we got here, all validation checks passed
        logger.info(f"Recording validation successful for {self.recording_info.recording_name}"
                    f"\n\t- {len(video_paths)} videos saved with {expected_frame_count} frames each"
                    f"\n\t- All timestamp files present and match video frame counts")
