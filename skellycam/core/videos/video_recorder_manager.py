import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Any

from pydantic import BaseModel, ValidationError, Field

from skellycam.core import CameraId
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.timestamps.full_timestamp import FullTimestamp
from skellycam.core.timestamps.multiframe_timestamp_logger import MultiframeTimestampLogger
from skellycam.core.videos.video_recorder import VideoRecorder
from skellycam.utilities.clean_up_empty_directories import recursively_remove_empty_directories

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
    fresh: bool = True

    video_recorders: Dict[CameraId, VideoRecorder]
    multi_frame_timestamp_logger: MultiframeTimestampLogger

    class Config:
        arbitrary_types_allowed = True

    @property
    def recording_info(self) -> "RecordingInfo":
        return RecordingInfo.from_video_recorder_manager(self)

    @property
    def number_of_frames_to_save(self) -> int:
        return sum([video_recorder.number_of_frames_to_write for video_recorder in self.video_recorders.values()])

    @property
    def frames_to_save(self) -> bool:
        return self.number_of_frames_to_save > 0

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               recording_folder: str):
        """
        NOTE - Does not add `first mf payload` to videos - call `add mf payload` after creation
        """

        logger.debug(f"Creating FrameSaver for recording folder {recording_folder}")

        recording_name = Path(recording_folder).name
        videos_folder = str(Path(recording_folder) / SYNCHRONIZED_VIDEOS_FOLDER_NAME)
        video_recorders = {}
        for camera_id, config in camera_configs.items():
            video_recorders[camera_id] = VideoRecorder.create(recording_name=recording_name,
                                                              videos_folder=videos_folder,
                                                              config=camera_configs[camera_id],
                                                              )

        return cls(recording_folder=recording_folder,
                   recording_name=recording_name,
                   camera_configs=camera_configs,
                   video_recorders=video_recorders,
                     multi_frame_timestamp_logger=MultiframeTimestampLogger.create(video_save_directory=videos_folder,
                                                                                  recording_name=recording_name)
                   )

    def add_multi_frame(self, mf_payload: MultiFramePayload):
        self.fresh = False
        logger.loop(f"Adding multi-frame {mf_payload.multi_frame_number} to video recorder for:  {self.recording_name}")
        mf_payload.lifespan_timestamps_ns.append({"start_adding_multi_frame_to_video_recorder": time.perf_counter_ns()})
        self._validate_multi_frame(mf_payload=mf_payload)
        mf_payload.lifespan_timestamps_ns.append({"before_add_multi_frame_to_video_savers": time.perf_counter_ns()})
        for camera_id, frame in mf_payload.frames.items():
            self.video_recorders[camera_id].add_frame(frame=frame)

        mf_payload.lifespan_timestamps_ns.append({"before_logging_multi_frame": time.perf_counter_ns()})
        self.multi_frame_timestamp_logger.log_multiframe(multi_frame_payload=mf_payload)

    def save_one_frame(self) -> Optional[bool]:
        """
        saves one frame from one video recorder
        """
        if not self.frames_to_save:
            return
        if not Path(self.recording_folder).exists():
            self._create_video_recording_folder()

        self._choose_and_save_one()
        return True

    def _choose_and_save_one(self):
        # get the camera with the most frames to write (of the first one with the max number of frames to write, if there is a tie)
        frame_write_lengths = {camera_id: video_recorder.number_of_frames_to_write for camera_id, video_recorder in
                               self.video_recorders.items()}
        camera_id = max(self.video_recorders, key=lambda x: self.video_recorders[x].number_of_frames_to_write)
        logger.loop(
            f"Saving one frame from camera {camera_id}, camera id vs frame write lengths: {frame_write_lengths}")
        self.video_recorders[camera_id].write_one_frame()



    def _save_folder_readme(self):
        with open(str(Path(self.recording_folder)/SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME), "w") as f:
            f.write(SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT)



    def _validate_multi_frame(self, mf_payload: MultiFramePayload):
        # Note - individual VideoRecorders will validate the frames' resolutions and whatnot
        if not self.camera_configs.keys() == mf_payload.frames.keys():
            raise ValidationError(f"CameraConfigs and MultiFramePayload frames do not match")

    def _create_video_recording_folder(self):
        Path(self.videos_folder).mkdir(parents=True, exist_ok=True)

    def finish_and_close(self):
        logger.debug(f"Finishing up...")
        finish_threads = []
        for recorder in self.video_recorders.values():
            finish_threads.append(threading.Thread(target=recorder.finish_and_close))
        for thread in finish_threads:
            thread.start()
        for thread in finish_threads:
            thread.join()
        self.close()

    def close(self):
        logger.debug(f"Closing {self.__class__.__name__} for recording: `{self.recording_name}`")
        for video_saver in self.video_recorders.values():
            video_saver.close()
        self.multi_frame_timestamp_logger.close()
        self.finalize_recording()
        # remove directories if empty
        recursively_remove_empty_directories(self.recording_folder)


    def finalize_recording(self):
        logger.debug(f"Finalizing recording: `{self.recording_name}`...")
        self.finalize_timestamps()
        self.save_recording_summary()
        self.validate_recording()
        # self._save_folder_readme() # TODO - uncomment this when ready, only save if recording is successful
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
