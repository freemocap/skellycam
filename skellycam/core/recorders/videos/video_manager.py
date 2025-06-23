import logging
import threading
import time
import uuid
from collections import deque
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.timestamps.recording_timestamps import RecordingTimestamps
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


class VideoManager(BaseModel):
    id: RecordingManagerIdString = Field(default_factory=lambda: str(uuid.uuid4))
    recording_info: RecordingInfo
    video_recorders: dict[CameraIdString, VideoRecorder]
    recording_timestamps: RecordingTimestamps
    mf_recarrays: deque[np.recarray] = Field(default_factory=deque)
    is_finished: bool = False
    class Config:
        arbitrary_types_allowed = True
    @classmethod
    def create(cls,
               recording_info: RecordingInfo,
                camera_configs: CameraConfigs,
               ):

        logger.debug(f"Creating RecordingManager for recording folder {recording_info.recording_name}")

        return cls(recording_info=recording_info,
                   recording_timestamps=RecordingTimestamps(recording_info=recording_info),
                   video_recorders={camera_id: VideoRecorder.create(camera_id=camera_id,
                                                                    recording_info=recording_info,
                                                                    config=config,
                                                                    ) for camera_id, config in camera_configs.items()}
                   )
    @property
    def camera_configs(self) -> CameraConfigs:
        """
        Returns the camera configurations for all cameras in the recording.
        """
        return {camera_id: video_recorder.camera_config for camera_id, video_recorder in self.video_recorders.items()}
    @property
    def frame_counts_to_save(self) -> dict[CameraIdString, int]:
        """
        Returns a dictionary of camera IDs to the number of frames that need to be saved for each camera.
        """
        return {camera_id: video_recorder.number_of_frames_to_write for camera_id, video_recorder in
                self.video_recorders.items()}


    def add_multi_frame_recarrays(self, mf_recarrays: list[np.recarray]):
        self.mf_recarrays.extend(mf_recarrays)


    def add_multi_frame(self, mf_payload: MultiFramePayload):
        logger.loop(
            f"Adding multi-frame {mf_payload.multi_frame_number} to video recorder for:  {self.recording_info.recording_name}")


        for camera_id in mf_payload.camera_ids:
            frame = mf_payload.get_frame(camera_id)
            self.video_recorders[camera_id].add_frame(frame=frame)
        self.recording_timestamps.add_multiframe(mf_payload)

    def _convert_mf_recarrays_to_payloads(self):
        while len(self.mf_recarrays) > 0:
            # Pop the first recarray from the deque
            mf_recarray = self.mf_recarrays.popleft()
            # Convert it to a MultiFramePayload
            self.add_multi_frame(MultiFramePayload.from_numpy_record_array(mf_recarray, apply_config_rotation=True))



    def try_save_one_frame(self) -> bool:
        """
        Checks if we are ready to save a frame, and if so, saves one frame.
        """

        if not Path(self.recording_info.videos_folder).exists():
            Path(self.recording_info.videos_folder).mkdir(parents=True, exist_ok=True)

        return self.save_one_frame()

    def save_one_frame(self) -> bool:
        """
        saves one frame from one video recorder
        """
        self._convert_mf_recarrays_to_payloads()
        if self.is_finished:
            logger.warning(f"RecordingManager for `{self.recording_info.recording_name}` is already finished. Cannot save more frames.")
            return False
        if max(self.frame_counts_to_save.values()) == 0:
            return False
        # Find the camera ID with the most frames to save
        camera_id_to_save = max(self.frame_counts_to_save, key=self.frame_counts_to_save.get)

        self.video_recorders[camera_id_to_save].write_one_frame()

        return True

    def _save_folder_readme(self):
        with open(str(Path(self.recording_info.videos_folder) / SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME), "w") as f:
            f.write(SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT)

    def finish_and_close(self):

        logger.info(f"Finishing up {len(self.video_recorders)} video recorders for recording: `{self.recording_info.recording_name}`")
        finish_threads = []
        self._convert_mf_recarrays_to_payloads()
        for recorder in self.video_recorders.values():
            finish_threads.append(threading.Thread(target=recorder.finish_and_close))
            finish_threads[-1].start()
        for thread in finish_threads:
            thread.join()
        self.close()


    def close(self):
        logger.debug(f"Closing {self.__class__.__name__} for recording: `{self.recording_info.recording_name}`")
        # Process any remaining frames before closing

        for recorder in self.video_recorders.values():
            recorder.close()
        self.finalize_recording()

    def finalize_recording(self):
        logger.debug(f"Finalizing recording: `{self.recording_info.recording_name}`...")
        self.recording_info.save_to_file()
        print("Starting to save timestamps...")
        tik = time.perf_counter()
        self.recording_timestamps.save_timestamps()
        print(f"Finished saving timestamps in {time.perf_counter() - tik:.2f} seconds")
        self._save_folder_readme()
        self.validate_recording()
        self.is_finished = True
        logger.success(
            f"Recording `{self.recording_info.recording_name} Successfully recorded to: {self.recording_info.recording_directory}")

    def validate_recording(self):
        logger.warning(
            "Recording validation is not implemented yet. This method should do things like check if all video/timestamp files have the same number of frames, etc.")
        pass
